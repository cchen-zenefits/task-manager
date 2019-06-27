from __future__ import absolute_import
from __future__ import unicode_literals

# Put Standard Library Imports Here:
import json
import logging

# Put Third Party/Django Imports Here:
from django.contrib.auth.models import User

# Put Zenefits Imports Here:
from extensions.security_context.context import excludeFromSecurityContext
from multi_org.reporting.custom.constants import DAYS_OF_WEEK_MAPPING
from multi_org.reporting.custom.utils import getParentCompanyData
from register_company.models import Company
from reports.models import CustomReport
from google_task_api import GoogleTaskActions

log = logging.getLogger(__name__)


class CustomReportsMetaData(object):
    def __init__(self, permission, context):
        super(CustomReportsMetaData, self).__init__()
        self._permission = permission
        self._context = context

    from __future__ import absolute_import

    
    @excludeFromSecurityContext()
    def execute(self, request):
        """
        Creates a new task.
        """
        data = json.dumps(request.data)
        if data.type == 'create':
            return GoogleTaskActions.createGoogleTask(data.title, data.description, data.category, data.dueDate, data.actions)