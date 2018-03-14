""" Remote Galaxy API adaptor """
from __future__ import unicode_literals

import logging
import time
from os.path import join

import bioblend
import requests
from bioblend.galaxy.client import ConnectionError
from bioblend.galaxy.objects import GalaxyInstance

from waves.wcore.adaptors.const import JobStatus, JobRunDetails
from exception import GalaxyAdaptorConnectionError
from waves.wcore.adaptors.api import ApiKeyAdaptor
from waves.wcore.adaptors.exceptions import AdaptorJobException, AdaptorExecException, AdaptorConnectException
from waves.wcore.models import JobOutput

logger = logging.getLogger(__name__)

__group__ = 'Galaxy'
__all__ = ['GalaxyJobAdaptor']


class GalaxyJobAdaptor(ApiKeyAdaptor):
    """
    This is Galaxy bioblend api WAVES adaptors, maps call to Galaxy API to expected behaviour from base class

    Expected parameters to init call (dictionary):

    **Init parameters:**
        :param host: the ip address where Galaxy is set up (default: http://localhost)
        :param username: remote user name in Galaxy server
        :param app_key: remote user's app key in Galaxy
        :param library_dir: remote library dir, where to place files in order to create galaxy histories

    """
    name = 'Galaxy remote tool adaptor (api_key)'
    _states_map = dict(
        new=JobStatus.JOB_QUEUED,
        queued=JobStatus.JOB_QUEUED,
        running=JobStatus.JOB_RUNNING,
        waiting=JobStatus.JOB_RUNNING,
        error=JobStatus.JOB_ERROR,
        ok=JobStatus.JOB_COMPLETED
    )
    library_dir = ""

    def __init__(self, command=None, protocol='http', host="localhost", port='', api_base_path='', api_endpoint='',
                 app_key=None, library_dir="", **kwargs):
        super(GalaxyJobAdaptor, self).__init__(command, protocol, host, port, api_base_path, api_endpoint,
                                               app_key, **kwargs)

        self.library_dir = library_dir

    @property
    def init_params(self):
        """
        Galaxy remote platform expected initialization parameters, defaults can be set in waves.wcore.adaptors.addons.env

        **returns**
            - host: Galaxy full host url
            - port: Galaxy host port
            - app_key: Galaxy remote user api_key
            - library_dir: Galaxy remote user library, no default
            - tool_id: Galaxy remote tool id, should be set for each Service, no default

        :return: A dictionary containing expected init params
        :rtype: dict
        """
        base_params = super(GalaxyJobAdaptor, self).init_params
        base_params.update(dict(library_dir=self.library_dir))
        return base_params

    def _connect(self):
        """ Create a bioblend galaxy object
        :raise: `waves.wcore.adaptors.addons.adaptors.galaxy.exception.GalaxyAdaptorConnectionError`
        """
        try:
            self.connector = GalaxyInstance(url=self.complete_url, api_key=self.app_key)
        except ConnectionError as exc:
            self._connected = False
            raise GalaxyAdaptorConnectionError(exc)

    def _disconnect(self):
        """ Setup Galaxy instance to 'disconnected' """
        self.connector = None
        self._connected = False

    def _prepare_job(self, job):
        """ - Create a new history from job data (hashkey as identifier)
            - upload job input files to galaxy in this newly created history
            - associate uploaded files galaxy id with input
        """
        import os
        try:
            history = self.connector.histories.create(name=job.title)
            job.remote_history_id = history.id
            logger.debug(u'New galaxy history to ' + history.id)
            if len(job.input_files) == 0:
                logger.info("No inputs files for galaxy service ??? %s ", job)
            for job_input_file in job.input_files:
                file_full_path = os.path.join(job.working_dir, job_input_file.value)
                upload = history.upload_file(file_full_path, file_name=job_input_file.name)
                job_input_file.remote_input_id = upload.id
                logger.debug('Remote data id %s for %s (%s)', job_input_file.remote_input_id, job_input_file.name,
                             job_input_file.value)
            # PATCH wait for upload complete completion (history state ok)
            state_history = self.connector.histories.get(id_=str(job.remote_history_id))
            # FIXME : to not wait until the end of time !
            t0 = time.clock()
            max_time = 360
            while state_history.state != 'ok' and time.clock() - t0 < max_time:
                time.sleep(2.5)
                state_history = self.connector.histories.get(id_=str(job.remote_history_id))
            if state_history.state != 'ok':
                raise AdaptorExecException('Maximum time reached to prepare job')
            job.message = 'Job prepared with %i args ' % job.job_inputs.count()
            logger.debug(u'History initialized [galaxy_history_id: %s]', job.slug)
            return job
        except bioblend.galaxy.client.ConnectionError as e:
            exc = GalaxyAdaptorConnectionError(e)
            job.message = exc.message
            raise exc
        except IOError as e:
            raise AdaptorJobException('File upload error %s' % e.message)

    def _run_job(self, job):
        """
        Launch the job with current parameters from associated history
        Args:
            job:
        """
        try:
            history = self.connector.histories.get(id_=str(job.remote_history_id))
            logger.debug("First attempts %s ", history.state)
            if history.state == 'ok':
                galaxy_tool = self.connector.tools.get(id_=self.command)
                if galaxy_tool and type(galaxy_tool) is not list:
                    logger.debug('Galaxy tool %s', galaxy_tool)
                    inputs = {}
                    for input_file in job.input_files:
                        inputs[input_file.remote_input_id] = input_file.name

                    for input_param in job.input_params:
                        if input_param.value != 'None' and input_param.value is not None:
                            inputs[input_param.name] = input_param.value
                    logger.debug(u'Inputs added ' + str(inputs))
                    output_data_sets = galaxy_tool.run(inputs, history=history, wait=False)
                    for data_set in output_data_sets:
                        job.remote_job_id = data_set.wrapped['creating_job']
                        logger.debug(u'Job ID ' + job.remote_job_id)
                        break
                    remote_job = self.connector.jobs.get(job.remote_job_id, full_details=True)
                    logger.debug('Job info %s', remote_job)
                    remote_outputs = remote_job.wrapped['outputs']
                    for remote_output in remote_outputs:
                        output_data = remote_outputs[remote_output]
                        logger.debug('Current output %s', remote_output)
                        logger.debug('Remote output details %s', output_data)
                        logger.debug('Remote output id %s', output_data['id'])

                        job_output = next((x for x in job.outputs.all() if x.api_name == remote_output), None)
                        if job_output is not None:
                            job_output.remote_output_id = str(output_data['id'])
                            job_output.save()
                        else:
                            logger.warn('Unable to retrieve job output in job description ! [%s]', remote_output)
                            logger.info('Searched in %s', [x.name + "/" + x.api_name for x in job.outputs.all()])
                            job.outputs.add(JobOutput.objects.create(_name=remote_output,
                                                                     job=job,
                                                                     remote_output_id=output_data['id']))
                    for data_set in output_data_sets:
                        logger.debug('Dataset Info %s', data_set)
                        job_output = next((x for x in job.outputs.all() if x.remote_output_id == data_set.id), None)
                        if job_output is not None:
                            logger.debug("Dataset updates job output %s with %s, %s",
                                         job_output,
                                         data_set.name,
                                         data_set.file_ext
                                         )
                            job_output.value = data_set.name
                            job_output.extension = data_set.file_ext
                            job_output.save()
                            logger.debug(u'Output value updated [%s - %s]' % (
                                data_set.id, '.'.join([data_set.name, data_set.file_ext])))
                    job.message = "Job queued"
                    return job
                else:
                    raise AdaptorExecException(None, 'Unable to retrieve associated tool %s' % self.command)
            else:
                raise AdaptorExecException(None, 'History not ready %s' % self.command)
        except requests.exceptions.RequestException as e:
            # TODO Manage specific Exception to be more precise
            job.message = 'Error in request for run %s ' % e.message
            raise AdaptorConnectException(e, 'RequestError')
        except bioblend.galaxy.client.ConnectionError as e:
            job.message = 'Connexion error for run %s:%s', (e.message, e.body)
            raise GalaxyAdaptorConnectionError(e)

    def _cancel_job(self, job):
        """ Jobs cannot be cancelled for Galaxy runners
        """
        pass

    def _job_status(self, job):
        try:
            remote_job = self.connector.jobs.get(job.remote_job_id)
            logger.debug('Current job remote state %s', remote_job.state)
            return remote_job.state
        except bioblend.galaxy.client.ConnectionError as e:
            job.message = 'Connexion error for run %s:%s', (e.message, e.body)
            logger.error('Galaxy connexion error %s', e)
            raise GalaxyAdaptorConnectionError(e)

    def _job_results(self, job):
        try:
            remote_job = self.connector.jobs.get(job.remote_job_id, full_details=True)
            logger.debug('Retrieve job results from Galaxy %s', job.remote_job_id)
            if remote_job:
                job.exit_code = remote_job.wrapped['exit_code']
                if remote_job.state == 'ok':
                    logger.debug('Job info %s', remote_job)
                    for job_output in job.outputs.all():
                        if job_output.remote_output_id:
                            logger.debug("Retrieved data from output %s:%s", job_output, job_output.remote_output_id)
                            self.connector.gi.histories.download_dataset(job.remote_job_id,
                                                                         job_output.remote_output_id,
                                                                         join(job.working_dir, job_output.file_path),
                                                                         use_default_filename=False)
                            logger.debug("Saving output to %s" % join(job.working_dir, job_output.file_path))
                # GET stdout / stderr from Galaxy
                with open(join(job.working_dir, job.stdout), 'a') as out, \
                        open(join(job.working_dir, job.stderr), 'a') as err:
                    try:
                        if remote_job.wrapped['stdout']:
                            out.write(remote_job.wrapped['stdout'])
                    except KeyError:
                        logger.warning('No stdout from remote job')
                        pass
                    try:
                        if remote_job.wrapped['stderr']:
                            err.write(remote_job.wrapped['stderr'])
                    except KeyError:
                        logger.warning('No stderr from remote job')
                        pass
                job.results_available = True
            else:
                logger.warning("Job not found %s ", job.remote_job_id)
            return job
        except bioblend.galaxy.client.ConnectionError as e:
            job.results_available = False
            job.message = 'Connexion error for run %s:%s', (e.message, e.body)
            raise GalaxyAdaptorConnectionError(e)

    def _job_run_details(self, job):
        remote_job = self.connector.jobs.get(job.remote_job_id, full_details=True)
        finished = None
        started = None
        extra = None
        if 'job_metrics' in remote_job.wrapped:
            for job_metric in remote_job.wrapped['job_metrics']:
                if job_metric['name'] == "end_epoch":
                    finished = job_metric['raw_value']
                if job_metric['name'] == "start_epoch":
                    started = job_metric['raw_value']
                if job_metric['name'] == "galaxy_slots":
                    extra = "%s %s" % (job_metric['value'], job_metric['title'])
        created = remote_job.wrapped['create_time']
        name = job.title
        exit_code = remote_job.wrapped['exit_code']
        details = JobRunDetails(job.id, str(job.slug), remote_job.id, name, exit_code,
                                created, started, finished, extra)
        logger.debug('Job Exit Code %s %s', exit_code, finished)
        # TODO see if remove history is needed
        # galaxy_allow_purge = self.connector.gi.config.get_config()['allow_user_dataset_purge']
        # self.connector.histories.delete(name=str(job.slug), purge=bool(galaxy_allow_purge))
        return details

    def test_connection(self):
        try:
            self.connector = self.connect()
            remote_user = self.connector.gi.users.get_current_user()
            return remote_user['username'] is not None and remote_user['deleted'] is False
        except ConnectionError as exc:
            self._connected = False
            raise GalaxyAdaptorConnectionError(exc)
        return False

    def connexion_string(self):
        return self.complete_url + '?api_key=' + str(self.app_key)

    @property
    def importer(self):
        from waves.adaptors.galaxy.importers import GalaxyToolImporter
        return GalaxyToolImporter(self)
