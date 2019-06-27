class InboxTask(ExtendedModel):

    history = HistoricalRecords()
    title = models.CharField(max_length=200, null=True)
    description = models.CharField(max_length=400, null=True)
    category = models.CharField(max_length=100, null=True)
    dueDate = models.DateTimeField(null=True, blank=True)
    eta = models.CharField(max_length=100, null=True)
    assigned = models.CharField(max_length=200, null=True)
    creator = models.CharField(max_length=200, null=True)

    def __init__(self, **args):
        actions = []
        for action in args:
            actions.append(TaskAction(action))

    def addAction(self, **args):
        for action in args:
            actions.append(TaskAction(action))

    def removeAction(self, **args):
        for action in args:
            actions.remove(TaskAction(action))

    class Meta:
        app_label = 'task'

class TaskAction(InboxTask):
    
    history = HistoricalRecords()
    action = models.CharField(max_length=500, null=True)
    completed = models.BooleanField(default=False)

    def __init__(self, action):
        self.action = action
    
    class Meta:
        app_label = 'action'