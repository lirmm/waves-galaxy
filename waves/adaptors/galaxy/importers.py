""" Galaxy remote platform Services / Workflow Import classes"""
from __future__ import unicode_literals

import logging
import os
import tempfile

import bioblend
import six
import swapper
from bioblend import ConnectionError
from bioblend.galaxy.objects import client

from waves.adaptors.galaxy.exception import GalaxyAdaptorConnectionError
from waves.wcore.adaptors.exceptions import *
from waves.wcore.adaptors.importer import AdaptorImporter
from waves.wcore.models.inputs import *
from waves.wcore.models.services import Submission, SubmissionOutput

Service = swapper.load_model("wcore", "Service")
logger = logging.getLogger(__name__)


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
        param_clazz = self._clazz_map.get(type_param, None)
        if not param_clazz:
            logger.warning("Unable to map %s", type_param)
            raise UnmanagedInputTypeException()
        else:
            return param_clazz

    def connect(self):
        """
        Connect to remote Galaxy Host
        :return:
        """
        self._adaptor.connect()
        self._tool_client = self._adaptor.connector.tools

    def load_tool_details(self, tool_id):
        try:
            details = self._tool_client.get(id_=tool_id, io_details=True, link_details=True)
            description = details.wrapped.get('description')
            # TODO add get retrieve existing services for updates
            self._service = Service.objects.create(name=details.name,
                                                   description=description,
                                                   short_description=description,
                                                   edam_topics=','.join(details.wrapped.get('edam_topics')),
                                                   edam_operations=','.join(details.wrapped.get('edam_operations')),
                                                   remote_service_id=tool_id,
                                                   version=details.version)
            self._submission = Submission.objects.create(name="Imported from Galaxy",
                                                         api_name="galaxy",
                                                         service=self._service,
                                                         availability=Submission.AVAILABLE_BOTH)
            self._service.submissions.add(self._submission)
            return details.wrapped.get('inputs'), details.wrapped.get('outputs'), []
        except ConnectionError as e:
            self.error(GalaxyAdaptorConnectionError(e))
            return None, None, None

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
                                 (Service(remote_service_id=y.id, name=y.name, version=y.version) for y in tool_list if
                                  y.wrapped['panel_section_name'] == x and y.wrapped['model_class'] == 'Tool'),
                                 key=lambda d: d.name)
                             ) for x in group_list]
            return service_list
        except ConnectionError as e:
            raise GalaxyAdaptorConnectionError(e)

    def import_exit_codes(self, tool_id):
        # TODO see if galaxy tool give this info
        return []

    def import_service_params(self, data):
        inputs = []
        logger.debug("Importing %i inputs ", len(data))
        for cur_input in data:
            logger.debug("Current Input %s: %s", cur_input.get('name'), cur_input.get('type'))
            tool_input_type = cur_input.get('type')
            logger.debug("Input type %s mapped to %s", tool_input_type, self.map_type(tool_input_type))
            service_input = None
            if tool_input_type == 'conditional':
                service_input = self._import_conditional_set(cur_input)
            elif tool_input_type == 'section':
                service_input = self.import_service_params([sect_input for sect_input in cur_input.get('inputs')])
            elif tool_input_type == 'repeat':
                repeat_group = self._import_repeat(cur_input)
                cur_input.repeat_group = repeat_group
                service_input = self.import_service_params([rep_input for rep_input in cur_input.get('inputs')])
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
        return inputs

    def _import_param(self, tool_input):
        try:
            if tool_input.get('is_dynamic', False):
                raise UnmanagedInputTypeException(
                    'Dynamic field \'%s\':%s ' % (tool_input.get('name'), tool_input.get('label')))

            logger.debug(self.get_clazz(tool_input.get('type', 'text')))
            logger.debug("tool_input values %s", tool_input)
            logger.debug(type(tool_input.get('optional')))
            if tool_input.get('hidden'):
                required = None
            else:
                required = not tool_input.get('optional')
            srv_input = self.get_clazz(
                tool_input.get('type', 'text')).objects.create(
                label=tool_input.get('label', tool_input.get('name', None)),
                name=tool_input.get('name'),
                default=tool_input.get('default', None),
                help_text=tool_input.get('help', ''),
                required=required,
                submission=self._submission
            )
            _import_func = getattr(self, '_import_' + tool_input.get('type', 'text'))
            logger.debug('import func %s ', _import_func.__name__)
            _import_func(tool_input, srv_input)
            if 'edam' in tool_input and 'edam_formats' in tool_input['edam']:
                srv_input.edam_formats = ','.join(tool_input['edam']['edam_formats'])
                srv_input.edam_datas = ','.join(tool_input['edam']['edam_data'])
            return srv_input
        except UnmanagedInputTypeException as e:
            logger.error(e)
            self.warn(e)
            return None
        except KeyError as e:
            logger.error(e)
            self.warn(
                UnManagedAttributeTypeException(
                    "Type:%s|Name:%s" % (tool_input.get('type', 'NA'), tool_input.get('name', 'NA'))))
            return None
        except AttributeError as e:
            self.warn(
                UnManagedAttributeException(
                    "Type:%s|Name:%s|Label:%s" % (tool_input.get('type', 'NA'), tool_input.get('name', 'NA'),
                                                  tool_input.get('label', 'NA'))))
            return None
        except Exception as e:
            logger.exception(e)
            self.error(Exception('UnexpectedError for input "%s" (%s)' % (tool_input['name'], e)))
            return None

    def _import_conditional_set(self, tool_input):
        conditional = self._import_param(tool_input.get('test_param'))
        logger.debug('Test param %s', tool_input['test_param'])
        logger.debug('Imported conditional %s', conditional)
        for related in tool_input.get('cases', []):
            when_value = related.get('value')
            for when_input in related['inputs']:
                when = self.get_clazz(
                    when_input.get('type', 'text')).objects.create(
                    label=when_input.get('label', when_input.get('name')),
                    name=when_input.get('name'),
                    default=when_input.get('value'),
                    help_text=when_input.get('help'),
                    required=False,
                    when_value=when_value,
                    submission=self._submission)
                when_input_type = when_input.get('type')
                try:
                    if when_input_type == 'conditional':
                        self.error(
                            UnmanagedInputTypeException(
                                "Unmanaged nested conditional inputs %s " % when_input.get('name')))
                        raise RuntimeWarning
                    logger.debug("Input type %s", when_input.get('type', 'text'))
                    _import_func = getattr(self, '_import_' + when_input.get('type', 'text'))
                    logger.debug('import func %s ', _import_func.__name__)
                    _import_func(when_input, when_input)
                except AttributeError as e:
                    self.error(Exception('UnexpectedError for input "%s" (%s)' % (when_input.get('name'), e)))
                except RuntimeWarning:
                    pass
                else:
                    conditional.dependents_inputs.add(when)
        return conditional

    def _import_text(self, tool_input, service_input):
        # TODO check if format needed
        pass

    def _import_boolean(self, tool_input, service_input):
        service_input.true_value = tool_input.get('truevalue', 'True')
        service_input.false_value = tool_input.get('falsevalue', 'False')
        logger.debug('ToolInputBoolean %s|%s', service_input.true_value, service_input.false_value)

    def _import_integer(self, tool_input, service_input):
        return self._import_number(tool_input, service_input)

    def _import_float(self, tool_input, service_input):
        return self._import_number(tool_input, service_input)

    def _import_number(self, tool_input, service_input):
        service_input.default = tool_input.get('value', '')
        service_input.min_val = tool_input.get('min', '')
        service_input.max_val = tool_input.get('max', '')

    def _import_data(self, tool_input, service_input):
        service_input.allowed_extensions = self._formatter.format_list(_get_input_value(tool_input, 'extensions'))
        service_input.multiple = _get_input_value(tool_input, 'multiple') is True

    def _import_select(self, tool_input, service_input):
        service_input.default = _get_input_value(tool_input, 'value')
        options = []
        for option in _get_input_value(tool_input, 'options'):
            if option[1].strip() == '':
                option[1] = 'None'
            options.append('|'.join([option[0], option[1]]))
        logger.debug('List options %s', options)
        service_input.list_elements = "\n".join(options)
        print service_input.list_elements

    def _import_repeat(self, tool_input, service_input=None):
        return RepeatedGroup.objects.create(name=_get_input_value(tool_input, 'name'),
                                            title=_get_input_value(tool_input, 'title'),
                                            max_repeat=_get_input_value(tool_input, 'max'),
                                            min_repeat=_get_input_value(tool_input, 'min'),
                                            default=_get_input_value(tool_input, 'default'),
                                            submission=self._submission)

    def _import_genomebuild(self, tool_input, service_input):
        return self._import_select(tool_input, service_input)

    def import_service_outputs(self, outputs):
        logger.debug(u'Managing service outputs')
        service_outputs = []
        index = 0
        for tool_output in outputs:
            # logger.debug(tool_output.keys())
            logger.debug(tool_output.items())
            service_output = SubmissionOutput.objects.create(label=tool_output.get('label', tool_output.get('name')),
                                                             name=tool_output.get('name'),
                                                             extension=tool_output.get('format'),
                                                             edam_format=tool_output.get('edam_format'),
                                                             edam_data=tool_output.get('edam_data'),
                                                             help_text=tool_output.get('label'),
                                                             submission=self._submission,
                                                             file_pattern="%s")
            if tool_output.get('name').startswith('$'):
                logger.debug("Value is depending on other input %s", tool_output.get('value'))
                pass
                # TODO repair relationship between inputs
                # input_related_name = service_output.description[2:-1]
                # service_output.from_input = True
                # related_input = Input.objects.get(name=input_related_name)
                # submission_related_output = RelatedInput(srv_input=related_input)
                # service_output.from_input_submission.add(submission_related_output, bulk=True)
                # service_output.description = "Issued from input '%s'" % input_related_name
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
        self._tool_client = client.ObjWorkflowClient(self._adaptor.connect())

    def _list_services(self):
        try:

            tool_list = self._tool_client.list()
            return [
                (y.id, y.name) for y in tool_list if y.published is True
            ]
        except ConnectionError as e:
            raise GalaxyAdaptorConnectionError(e)

    def _list_remote_inputs(self, tool_id):
        logger.warn('Not Implemented yet')
        wl = self._tool_client.get(id_=tool_id)
        wc = bioblend.galaxy.workflows.WorkflowClient(self._tool_client.gi)
        with tempfile.TemporaryFile() as tmp_file:
            wc.export_workflow_to_local_path(workflow_id=tool_id,
                                             file_local_path=os.path.join(tempfile.gettempdir(), tmp_file.name),
                                             use_default_filename=False)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('inputs %s', wl.inputs)
            logger.debug('inputs_i %s', wl.data_input_ids)
            logger.debug('inputs %s', wl.inputs['0'])
            logger.debug('labels %s', wl.input_labels)
            logger.debug('runnable %s', wl.is_runnable)
        for id_step in wl.sorted_step_ids():
            step = wl.steps[id_step]
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('step  %s %s %s:', step.type, ' name ', step.name)
                logger.debug('input_steps %s', step.input_steps)
                logger.debug('tool_inputs %s', step.tool_inputs)
                logger.debug('tool_id %s', step.tool_id)
        return wl.inputs

    def _list_remote_outputs(self, tool_id):
        logger.warn('Not Implemented yet')
        return []

    def import_exit_codes(self, tool_id):
        logger.warn('Not Implemented yet')
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
                                      submission=self._service,
                                      default=dic['value'],
                                      mandatory=True)
            logger.debug('Service input %s ', service_input)
            service_inputs.append(service_input)
        return service_inputs
