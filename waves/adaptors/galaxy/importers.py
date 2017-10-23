""" Galaxy remote platform Services / Workflow Import classes"""
from __future__ import unicode_literals

import logging
import os
import tempfile
import json
import bioblend
import six
from bioblend import ConnectionError
from bioblend.galaxy.objects import client

from waves.adaptors.galaxy.exception import GalaxyAdaptorConnectionError
from waves.wcore.adaptors.exceptions import *
from waves.wcore.adaptors.importer import AdaptorImporter
from waves.wcore.models.inputs import *
from waves.wcore.models import get_submission_model, SubmissionOutput, get_service_model, Runner

Submission = get_submission_model()
Service = get_service_model()


def _get_input_value(tool_input, field, default=''):
    return tool_input[field] if field in tool_input and tool_input[field] != '' else default


class GalaxyToolImporter(AdaptorImporter):
    """ Allow Service to automatically import submission parameters from Galaxy bioblend API """
    #: List of tools categories which are not meaning a 'WAVES' service tool
    _unwanted_categories = [None, 'Get Data', 'Filter and sort', 'Collection Operations', 'Graph/Display Data',
                            'Send Data', 'Text Manipulation', 'Fetch Alignments', ]

    # TODO share constants with waves_addons-webapp (moved in main adaptors module ?)
    _type_map = dict(
        text='text',
        boolean='boolean',
        integer='int',
        float='float',
        data='file',
        select='list',
        conditional='list',
        data_collection='file',
        genomebuild='list',
    )

    _clazz_map = dict(
        text=TextParam,
        boolean=BooleanParam,
        integer=IntegerParam,
        float=DecimalParam,
        data=FileInput,
        select=ListParam,
        conditional=ListParam,
        data_collection=FileInput,
        genomebuild=ListParam,
    )

    def get_clazz(self, type_param):
        self._logger.debug('Mapping %s' % type_param)
        param_clazz = self._clazz_map.get(type_param, None)
        if param_clazz is None:
            self._logger.warning("Unable to map %s", type_param)
            raise UnmanagedInputTypeException()
        else:
            return param_clazz

    def __init__(self, adaptor):
        super(GalaxyToolImporter, self).__init__(adaptor)

    def connect(self):
        """
        Connect to remote Galaxy Host
        :return:
        """
        self.adaptor.connect()
        self._tool_client = self.adaptor.connector.tools

    def load_tool_params(self, tool_id, for_submission):
        details = self._tool_client.get(id_=tool_id, io_details=True, link_details=True)
        self._logger.debug('Tools detailed: \n%s ' % json.dumps(details.wrapped))
        self._logger.debug('----------- IMPORT INPUTS --------------')
        for_submission.inputs = self.import_service_params(details.wrapped.get('inputs'))
        self._logger.debug('----------- // INPUTS --------------')
        self._logger.debug('----------- IMPORT OUTPUTS --------------')
        for_submission.outputs = self.import_service_outputs(details.wrapped.get('outputs'))
        self._logger.debug('----------- // OUTPUTS --------------')
        self._logger.debug('----------- IMPORT EXITCODES --------------')
        for_submission.exit_code = self.import_exit_codes([])
        self._logger.debug('----------- // EXITCODES --------------')

    def load_tool_details(self, tool_id):
        """
        Load remote tool details, return a initialized Service object (not saved)
        :param tool_id:
        :return: Service
        """
        try:
            details = self._tool_client.get(id_=tool_id, io_details=False, link_details=False)
            description = details.wrapped.get('description')
            # TODO add get retrieve existing services for updates
            service = Service(name=details.name,
                              description=description,
                              short_description=description,
                              edam_topics=','.join(details.wrapped.get('edam_topics', [])),
                              edam_operations=','.join(
                                  details.wrapped.get('edam_operations', [])),
                              remote_service_id=tool_id,
                              version=details.version)
            return service
        except ConnectionError as e:
            self.error(GalaxyAdaptorConnectionError(e))
            return None

    def _list_services(self):
        """
        List available tools on remote Galaxy server, filtering with ``_unwanted_categories``
        Group items by categories

        :return: A list of tuples corresponding to format used in Django for Choices
        """
        try:
            tool_list = self._tool_client.list()
            group_list = sorted(set(map(lambda x: x.wrapped['panel_section_name'], tool_list)), key=lambda z: z)
            group_list = [x for x in group_list if x not in self._unwanted_categories]
            service_list = [(x,
                             sorted(
                                 (Service(remote_service_id=y.id, name=y.name, version=y.version,
                                          description=y.wrapped['description']) for y in tool_list if
                                  y.wrapped['panel_section_name'] == x and y.wrapped['model_class'] == 'Tool'),
                                 key=lambda d: d.name)
                             ) for x in group_list]
            return [(x[0], [
                (y.remote_service_id, y.name + ' ' + y.version + (' (%s)' % y.description if y.description else '')) for
                y in x[1]])
                    for x in service_list]
        except ConnectionError as e:
            raise GalaxyAdaptorConnectionError(e)

    def import_exit_codes(self, exit_codes):
        # TODO see if galaxy tool give this info
        return []

    def import_service_params(self, data):
        inputs = []
        self._logger.debug("%i inputs to import ", len(data))
        self._logger.debug("-----------------------")
        i = 1
        for cur_input in data:
            tool_input_type = self.map_type(cur_input.get('type'))
            clazz = self.get_clazz(cur_input.get('type'))
            self._logger.info("Input #%i %s %s %s", i, cur_input.get('label'), cur_input.get('name'),
                              cur_input.get('type'))
            self._logger.debug('Input details: \n%s ' % json.dumps(cur_input))
            self._logger.info("%s mapped to %s (%s)", cur_input.get('type'), tool_input_type, clazz.__class__.__name__)
            service_input = None
            if tool_input_type == 'section':
                service_input = self.import_service_params(cur_input.get('inputs'))
            elif tool_input_type == 'repeat':
                repeat_group = self._import_repeat(cur_input)
                cur_input.repeat_group = repeat_group
                service_input = self.import_service_params(cur_input.get('inputs'))
                for srv_input in service_input:
                    # print "srv_input", srv_input
                    srv_input.repeat_group = repeat_group
            elif tool_input_type == 'expand':
                self.warn(UnmanagedInputTypeException("Expand"))
            else:
                service_input = self._import_param(cur_input)
            if service_input is not None:
                if type(service_input) is list:
                    inputs.extend(service_input)
                else:
                    inputs.append(service_input)
            i += 1
        return inputs

    def _import_param(self, tool_input):
        """
        Import a single parameter and return a AParam object (or one of its subclass)
        :param tool_input: Received input
        :return: AParam
        """
        try:
            self._logger.info(
                'Import param ' + tool_input.get('name', 'NoName') + "/" + tool_input.get('label', 'NoLabel'))
            if tool_input.get('is_dynamic', False):
                raise UnmanagedInputTypeException(
                    'Dynamic field \'%s\':%s ' % (tool_input.get('name'), tool_input.get('label')))
            if tool_input.get('hidden'):
                required = None
            else:
                required = not tool_input.get('optional')
            ParamClazz = self.get_clazz(tool_input.get('type', 'text'))
            self._logger.info('Creating a %s ' % ParamClazz.__name__)
            srv_input = ParamClazz.objects.create(
                label=tool_input.get('label', tool_input.get('name', 'NoLabel')),
                name=tool_input.get('name', 'NoName'),
                default=tool_input.get('default', None),
                help_text=tool_input.get('help', ''),
                required=required,
                submission=self.submission
            )
            # Add special type import data
            _import_func = getattr(self, '_import_' + tool_input.get('type', 'text'))
            self._logger.info('Import function %s ', _import_func.__name__)
            _import_func(tool_input, srv_input)
            if 'edam' in tool_input and 'edam_formats' in tool_input['edam']:
                srv_input.edam_formats = \
                    ','.join([edam_format for edam_format in tool_input['edam']['edam_formats'] if edam_format])
                srv_input.edam_datas = \
                    ','.join([edam_data for edam_data in tool_input['edam']['edam_data'] if edam_data])
            srv_input.save()
            return srv_input
        except UnmanagedInputTypeException as e:
            self._logger.error(e)
            self.warn(e)
            return None
        except KeyError as e:
            self._logger.error(e)
            self.warn(
                UnManagedAttributeTypeException(
                    "Type:%s|Name:%s" % (tool_input.get('type', 'NA'), tool_input.get('name', 'NA'))))
            return None
        except AttributeError as e:
            self.warn(
                UnManagedAttributeException(
                    "Type:%s|Name:%s|Label:%s" % (tool_input.get('type', 'NA'), tool_input.get('name', 'NA'),
                                                  tool_input.get('label', 'NA'))))
            self._logger.warning("Attribute error %s", e.message)
            return None
        except Exception as e:
            self._logger.exception(e)
            self.error(Exception('UnexpectedError for input "%s" (%s)' % (tool_input['name'], e)))
            return None

    def _import_conditional(self, tool_input, srv_input):
        self._logger.info('Import conditional set %s ' % tool_input.get('test_param'))
        test_data = tool_input.get('test_param')
        srv_input.label = test_data.get('label', tool_input.get('name', 'NoLabel'))
        srv_input.name = test_data.get('name', 'NoName')
        srv_input.default = test_data.get('value', None)
        srv_input.help_text = test_data.get('help', '')
        srv_input.required = not test_data.get('optional')
        self._import_select(test_data, srv_input)
        self._logger.debug('Imported conditional %s', srv_input)
        for related in tool_input.get('cases', []):
            self._logger.info('Import case ' + related.get('value'))
            for when_input in related['inputs']:
                when = self._import_param(when_input)
                when.when_value = related.get('value')
                when.parent = srv_input
                when.save()
                srv_input.dependents_inputs.add(when)

    def _import_text(self, tool_input, service_input):
        # TODO check if format needed
        pass

    def _import_boolean(self, tool_input, service_input):
        service_input.true_value = tool_input.get('truevalue', 'True')
        service_input.false_value = tool_input.get('falsevalue', 'False')
        service_input.required = False
        self._logger.debug('ToolInputBoolean %s|%s', service_input.true_value, service_input.false_value)

    def _import_integer(self, tool_input, service_input):
        return self._import_number(tool_input, service_input)

    def _import_float(self, tool_input, service_input):
        return self._import_number(tool_input, service_input)

    def _import_number(self, tool_input, service_input):
        service_input.default = tool_input.get('value', '')
        service_input.min_val = tool_input.get('min', '')
        service_input.max_val = tool_input.get('max', '')

    def _import_data(self, tool_input, service_input):
        allowed_extensions = ", ".join([".%s" % val for val in _get_input_value(tool_input, 'extensions', [])])
        self._logger.debug("Allowed extensions: %s " % allowed_extensions)
        service_input.allowed_extensions = allowed_extensions
        service_input.multiple = _get_input_value(tool_input, 'multiple') is True
        self._logger.debug("Multiple: %s " % service_input.multiple)

    def _import_select(self, tool_input, service_input):
        service_input.default = _get_input_value(tool_input, 'value')
        options = []
        for option in _get_input_value(tool_input, 'options'):
            if option[1].strip() == '':
                option[1] = 'None'
            options.append('|'.join([option[0], option[1]]))
        self._logger.debug('List options %s', options)
        service_input.list_elements = "\n".join(options)

    def _import_repeat(self, tool_input, service_input=None):
        return RepeatedGroup.objects.create(name=_get_input_value(tool_input, 'name'),
                                            title=_get_input_value(tool_input, 'title'),
                                            max_repeat=_get_input_value(tool_input, 'max'),
                                            min_repeat=_get_input_value(tool_input, 'min'),
                                            default=_get_input_value(tool_input, 'default'),
                                            submission=self.submission)

    def _import_genomebuild(self, tool_input, service_input):
        return self._import_select(tool_input, service_input)

    def import_service_outputs(self, outputs):
        self._logger.debug(u'Managing service outputs')
        service_outputs = []
        index = 0
        for tool_output in outputs:
            # self._logger.debug(tool_output.keys())
            self._logger.debug(tool_output.items())
            if tool_output.get('label').startswith('$'):
                input_api_name = tool_output.get('label')[2:-1]
                label = tool_output.get('name')
            else:
                input_api_name = tool_output.get('name')
                label = tool_output.get('label') if tool_output.get('label', '') != '' else tool_output.get('name')
            service_output = SubmissionOutput(label=label,
                                              name=tool_output.get('name'),
                                              api_name=input_api_name,
                                              extension=".%s" % tool_output.get('format'),
                                              edam_format=tool_output.get('edam_format'),
                                              edam_data=tool_output.get('edam_data'),
                                              submission=self.submission,
                                              file_pattern=tool_output.get('name'))
            if tool_output.get('label').startswith('$'):
                input_related_name = tool_output.get('label')[2:-1]
                self._logger.debug("Value is depending on other input %s", tool_output.get('label')[2:-1])
                related_input = AParam.objects.get(name=input_related_name, submission=self.submission)
                self._logger.info('Found related \'%s\'', related_input)
                service_output.from_input = related_input
                service_output.file_pattern = "%s"
                service_output.description = "Issued from input '%s'" % input_related_name
            service_output.save()
            service_outputs.append(service_output)
            index += 1
        return service_outputs

    def _import_section(self, section):
        return self.import_service_params(section['inputs'])


class GalaxyWorkFlowImporter(GalaxyToolImporter):
    """
    Galaxy Workflow service importer
    """
    workflow = None
    workflow_full_description = None

    def connect(self):
        """
        Connect to remote Galaxy Host
        :return:
        """
        self._tool_client = client.ObjWorkflowClient(self.adaptor.connect())

    def _list_services(self):
        try:

            tool_list = self._tool_client.list()
            return [
                (y.id, y.name) for y in tool_list if y.published is True
            ]
        except ConnectionError as e:
            raise GalaxyAdaptorConnectionError(e)

    def _list_remote_inputs(self, tool_id):
        self._logger.warn('Not Implemented yet')
        wl = self._tool_client.get(id_=tool_id)
        wc = bioblend.galaxy.workflows.WorkflowClient(self._tool_client.gi)
        with tempfile.TemporaryFile() as tmp_file:
            wc.export_workflow_to_local_path(workflow_id=tool_id,
                                             file_local_path=os.path.join(tempfile.gettempdir(), tmp_file.name),
                                             use_default_filename=False)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug('inputs %s', wl.inputs)
            self._logger.debug('inputs_i %s', wl.data_input_ids)
            self._logger.debug('inputs %s', wl.inputs['0'])
            self._logger.debug('labels %s', wl.input_labels)
            self._logger.debug('runnable %s', wl.is_runnable)
        for id_step in wl.sorted_step_ids():
            step = wl.steps[id_step]
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug('step  %s %s %s:', step.type, ' name ', step.name)
                self._logger.debug('input_steps %s', step.input_steps)
                self._logger.debug('tool_inputs %s', step.tool_inputs)
                self._logger.debug('tool_id %s', step.tool_id)
        return wl.inputs

    def _list_remote_outputs(self, tool_id):
        self._logger.warn('Not Implemented yet')
        return []

    def import_exit_codes(self, tool_id):
        self._logger.warn('Not Implemented yet')
        return []

    def load_tool_details(self, tool_id):
        self.workflow = self._tool_client.get(id_=tool_id)
        self.workflow_full_description = self.workflow.export()
        # TODO refactor this to import values from workflow
        return Service.objects.create(name='new workflow',
                                      version='1.0',
                                      short_description="")

    def import_service_params(self, data):
        service_inputs = []
        for dat in six.iteritems(data):
            dic = dat[-1]
            service_input = TextParam(name=dic['label'],
                                      label=dic['label'],
                                      submission=self.service,
                                      default=dic['value'],
                                      mandatory=True)
            self._logger.debug('Service input %s ', service_input)
            service_inputs.append(service_input)
        return service_inputs
