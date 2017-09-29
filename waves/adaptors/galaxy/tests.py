"""Galaxy Adaptor test cases """
from __future__ import unicode_literals

import logging
import unittest
from os.path import dirname, join

from django.conf import settings
from django.test import TestCase

from waves.wcore.adaptors.exceptions import AdaptorConnectException
from waves.wcore.models import Service, Job, JobInput, JobOutput, AParam
from waves.wcore.tests.tests_utils import TestJobWorkflowMixin
from waves.adaptors.galaxy.tool import GalaxyJobAdaptor
from waves.adaptors.galaxy.workflow import GalaxyWorkFlowAdaptor
from waves.adaptors.galaxy.utils import skip_unless_galaxy, skip_unless_tool

logger = logging.getLogger(__name__)


@skip_unless_galaxy()
class GalaxyRunnerTestCase(TestCase, TestJobWorkflowMixin):
    def setUp(self):
        self.adaptor = GalaxyJobAdaptor(host=settings.WAVES_TEST_GALAXY_HOST,
                                        protocol=settings.WAVES_TEST_GALAXY_PROTOCOL,
                                        port=settings.WAVES_TEST_GALAXY_PORT,
                                        app_key=settings.WAVES_TEST_GALAXY_API_KEY)
        super(GalaxyRunnerTestCase, self).setUp()
        # ShortCut for adaptor GI
        try:
            self.gi = self.adaptor.connect()
        except AdaptorConnectException:
            self.skipTest('Unable to connect to remote')
        else:
            logger.info('Adaptor config: %s' % self.adaptor.dump_config())

    @classmethod
    def setUpClass(cls):
        super(GalaxyRunnerTestCase, cls).setUpClass()

    def test_list_galaxy_tools(self):
        """
        Test listing of available galaxy tools
        """
        tools = self.adaptor.importer.list_services()
        self.assertGreater(len(tools), 0)
        for tool in tools:
            logger.info('Found tool : %s', tool)

    @skip_unless_tool("MAF_To_Fasta1")
    def test_import_tool(self):
        service, submission = self.adaptor.importer.import_service("MAF_To_Fasta1")

        self.assertIsNotNone(service)
        self.assertGreater(submission.inputs.count(), 0)

    @skip_unless_tool("toolshed.g2.bx.psu.edu/repos/rnateam/mafft/rbc_mafft/7.221.1")
    def test_import_mafft(self):

        service, submission = self.adaptor.importer.import_service(
            "toolshed.g2.bx.psu.edu/repos/rnateam/mafft/rbc_mafft/7.221.1")
        self.assertIsNotNone(service)
        submission.adaptor = self.adaptor
        # print "service init_params", service.runner.adaptor.init_params
        # job.adaptor = service.adaptor
        job = Job.objects.create(submission=submission)
        self.assertEqual(job.outputs.count(), 2)
        job.job_inputs.add(JobInput.objects.create(param_type=AParam.TYPE_FILE,
                                                   value=join(dirname(__file__), 'fixtures', 'tests', 'mafft.fasta'),
                                                   name="inputs",
                                                   command_type=AParam.OPT_TYPE_SIMPLE,
                                                   job=job))

        for output in submission.outputs.all():
            logger.debug("Adding expected output %s ", output.name)
            job.outputs.add(JobOutput.objects.create(job=job,
                                                     _name=output.name,
                                                     value=output.name,
                                                     extension=output.extension))
        job.save()
        self.run_job_workflow(job)

    def tearDown(self):
        """
        Delete created histories on remote Galaxy server after classic tearDown
        Returns:
            None
        """
        super(GalaxyRunnerTestCase, self).tearDown()
        if not settings.WAVES_DEBUG_GALAXY:
            for history in self.gi.histories.list():
                logger.debug('Deleting history %s:%s ', history.name, history.id)
                self.gi.histories.delete(history.id, purge=self.gi.gi.config.get_config()['allow_user_dataset_purge'])


@skip_unless_galaxy()
class GalaxyWorkFlowRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.adaptor = GalaxyWorkFlowAdaptor(host=settings.WAVES_TEST_GALAXY_HOST,
                                             protocol=settings.WAVES_TEST_GALAXY_PROTOCOL,
                                             port=settings.WAVES_TEST_GALAXY_PORT,
                                             app_key=settings.WAVES_TEST_GALAXY_API_KEY)
        super(GalaxyWorkFlowRunnerTestCase, self).setUp()

    @property
    def importer(self):
        return self.adaptor.importer

    def test_list_galaxy_workflow(self):
        services = self.importer.list_services()
        if len(services) > 0:
            self.assertGreaterEqual(len(services), 0)
            for serv in services:
                logger.debug('Service %s is retrieved', serv)
        else:
            self.skipTest("No remote workflows ")

    @unittest.skip('WorkFlow not available')
    def test_import_new_workflow(self):
        workflows = self.importer.list_services()
        if len(workflows) > 0:
            for remote_service in workflows:
                self.importer.import_service(tool_id=remote_service[0])
        else:
            self.skipTest("No remote workflows ")

    @unittest.skip('WorkFlow not available')
    def test_update_existing_workflow(self):
        service = Service(runner='waves.adaptors.galaxy.workflow.GalaxyWorkFlowAdaptor')
        self.assertGreaterEqual(len(service), 0)
        for updated in service[0:1]:
            # just try for the the first one
            remote_tool_param = updated.srv_run_params.get(name='remote_tool_id')
            logger.debug('Remote too id for service %s : %s', updated, remote_tool_param.value)
            self.importer.import_remote_service(tool_id=remote_tool_param.value)
