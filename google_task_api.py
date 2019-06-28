from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import threading
import json

"""
The purpose of the below function is to take in the different parameters that are passed in from YP, the same ones sent to our database models,
and create the different tasks given these different inputs. The second function will be used to read when tasks are checked off or modified, and
in turn change those in the DB to reflect on the YP interface.
"""

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/tasks.readonly', 'https://www.googleapis.com/auth/tasks']

class GoogleTaskActions:

    def getCredentials(self):
        """
        Gets credentials for the Google Tasks API.
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server()
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('tasks', 'v1', credentials=creds)
        return service


    #####################
    # YP -> Google Tasks
    #####################

    def createGoogleTaskCategory(self, title):
        """
        Create a Google Task category given a title.
        """
        service = self.getCredentials()
        taskList = {
            'title': title,
        }
        category = service.tasklists().insert(body=taskList).execute()
        # CATEGORIES[title] = task['id']
        return category


    def getGoogleTaskCategories(self):
        """
        Return all Google Task categories.
        """
        #NOTE: Make this only return the ones constructed by us.

        service = self.getCredentials()
        taskLists = service.tasklists().list().execute()
        return taskLists


    def getGoogleTaskListById(self, taskListId):
        """
        Get task list by ID.
        """
        service = self.getCredentials()
        taskList = service.tasklists().get(tasklist=taskListId).execute()
        return taskList


    def createGoogleTask(self, title, description, categoryName, dueDate, estimatedDuration, actions):
        """
        Creates the different tasks into the Google's Task manager, and create separate tasks for all the
        sub-actions of each task.
        """
        service = self.getCredentials()
        
        # To see whether or not the passed in category already exists.
        categories = self.getGoogleTaskCategories()
        found = False
        for cat in categories['items']:
            if cat['title'] == categoryName:
                found = True
                categoryFound = cat
                break
        if not found:
            categoryId = self.createGoogleTaskCategory(categoryName)['id']
        else:
            categoryId = categoryFound['id']
        
        # Create the parent task
        parentTask = {
            'title': title,
            'notes': description + "\n\nEstimated Duration: " + str(estimatedDuration) + " minutes",
            'due': dueDate,
        }

        createdTasks = {}
        parent = service.tasks().insert(tasklist=categoryId, body=parentTask).execute()
        createdTasks['Parent'] = parent

        # Create the children tasks from the actions
        childrenTasks = []
        for action in actions:
            time = action.get('estimatedDuration')
            if not time:
                notes = action['description']
            else:
                notes = action['description'] + "\n\nEstimated Duration: " + str(action['estimatedDuration']) + " minutes"
            childDueDate = action.get('dueDate')
            childTask = {
                # 'id': action['id'],
                'title': action['title'],
                'notes': notes,
                'due': childDueDate,
            }
            task = service.tasks().insert(tasklist=categoryId, body=childTask, parent=parent['id']).execute()
            childrenTasks.append(task)
        createdTasks['Children'] = childrenTasks
        return createdTasks


    def getGoogleTasksByCategory(self, taskListId):
        """
        Returns all tasks under a certain category.
        """
        service = self.getCredentials()
        tasks = service.tasks().list(tasklist=taskListId, showCompleted=True, showDeleted=True, showHidden=True).execute()
        return tasks


    def getGoogleTaskByTaskListAndId(self, taskList, taskId):
        """
        Returns a task object given a taskList and a taskId.
        """
        service = self.getCredentials()
        task = service.tasks().get(tasklist=taskList, task=taskId).execute()
        return task


    #TODO: Figure out how to be able to change categories and input categories.

    def modifyGoogleTask(self, taskId, title=None, description=None, category=None, dueDate=None, estimatedDuration=None, actions=[]):
        #(id=None, title, description=None, category='@default', dueDate, estimatedDuration, actions):
        """
        Modifies Google Task event from YP change.
        """
        service = self.getCredentials()
        task = service.tasks().get(tasklist=category, task=taskId).execute()
        if title:
            task['title'] = title
        if description:
            task['notes'] = description
        if dueDate:
            task['due'] = dueDate

        result = service.tasks().update(tasklist=category, task=task['id'], body=task).execute()

        for action in actions:
            task = service.tasks().get(tasklist=category, task=taskId).execute()
            task['title'] = action['title']
            task['notes'] = action['description']
            task['due'] = action['dueDate']
            
            result = service.tasks().update(tasklist=category, task=task['id'], body=task).execute()
            return {'success': False}

        return {'success': True}


    def completeGoogleTask(taskId, category):
        """
        Marks a Google Task as complete.
        """
        service = self.getCredentials()
        task = service.tasks().get(tasklist=category, task=taskId).execute()
        task['status'] = 'completed'
        try:
            result = service.tasks().update(tasklist='@default', task=task['id'], body=task).execute()
        except:
            print("Error trying to mark task as incomplete!")
            return {'success': False}
        return {'success': True}


    def uncompleteGoogleTask(taskId, category):
        """
        Marks a Google Task as incomplete.
        """
        service = self.getCredentials()
        task = service.tasks().get(tasklist=category, task=taskId).execute()
        task['status'] = 'needsAction'
        try:
            result = service.tasks().update(tasklist='@default', task=task['id'], body=task).execute()
        except:
            print("Error trying to mark task as incomplete!")
            return {'success': False}
        return {'success': True}


    #####################
    # Google Tasks -> YP
    #####################

    def compareKeys(currDict, formerDict):
        """
        Compare two dictionaries and return differences. CurrDict is source of truth.

        #NOTE: Can optimize by using the fact that when things are updated, the updated
        key in the object gets updated.
        """
        diff = {}
        for key in currDict:
            if currDict.get(key) != formerDict.get(key):
                diff[key] = currDict.get(key)
        return diff


    def compareGoogleResponses(formerResponse, currentResponse):
        """
        Determine the differences between the former Google Task categories, and the current Google Task categories,
        and return the differences with key-value pairs of IDs: attributes. Current categories is the source of truth,
        and we will override what exist in the formerCategories as incorrect.

        Runtime is O(N^2), could be reason for slow computation.
        """
        differences = {}
        deletedItems = {}
        newItems = {}
        former = formerResponse['items']
        current = currentResponse['items']

        for currItem in current:
            currId = currItem['id']
            found = False
            for formerItem in former:
                if formerItem['id'] == currId:
                    found = True
                    toCompare = formerItem
                    former.remove(formerItem)
                    pass
            if not found:
                newItems[currId] = currItem
                # differences.append({currId: currItem})
            else:
                keyDiff = compareKeys(currItem, toCompare)

                # No differences = do nothing.
                if keyDiff:
                    differences[currId] = keyDiff
                # differences.append({currId: keyDiff})
        
        for deleted in former:
            deletedItems[deleted["id"]] = deleted

        return newItems, differences, deletedItems


    def determineChangesFromTasks():
        """
        This function will determine what were the changes that happened 
        """
        # Keep track of differences between categories and tasks.
        differences = {}
        differences['newTasks'] = {}
        differences['changedTasks'] = {}
        differences['deletedTasks'] = {}

        currentState = {}
        currentState['tasks'] = {}

        with open('formerState.json', 'r+') as json_file:
            try:
                formerState = json.load(json_file)
            except ValueError:
                # This means the file is empty.
                currentCategories = self.getGoogleTaskCategories()
                currentState['categories'] = currentCategories
                differences['newCategories'] = currentCategories
                for category in currentCategories['items']:
                    categoryId = category['id']
                    currentTask = getGoogleTasksByCategory(categoryId)
                    differences['newTasks'][categoryId] = currentTask
                    currentState['tasks'][categoryId] = currentTask
                json_string = json.dump(differences, json_file)
                json_file.close()
                return json_string

            json_file.close()

        # Keep track of the current state to eventually replace formerState
        currentState = {}
        currentState['tasks'] = {}

        # Finding difference between categories of former and current states.
        formerCategories = formerState['categories']
        currentCategories = self.getGoogleTaskCategories()
        differences['newCategories'], differences['changedCategories'], differences['deletedCategories'] = compareGoogleResponses(formerCategories, currentCategories)

        # # Take all the deleted categories, and remove all their respective tasks.
        # for categoryId in differences['deletedCategories']:
        #     differences['deletedTasks'][categoryId] = getGoogleTasksByCategory(categoryId)
        
        currentState['categories'] = currentCategories

        # Finding difference between tasks of former and current states by iterating through all of the current categories.
        formerTasksAndCategories = formerState['tasks']
        for category in currentCategories['items']:
            categoryId = category['id']
            try:
                formerTasks = formerTasksAndCategories[categoryId]
            except KeyError:
                # This means this is a completely new category.
                currentTasks = getGoogleTasksByCategory(categoryId)
                currentState['tasks'][categoryId] = currentTasks
                differences['newTasks'][categoryId] = currentTasks
                continue
            currentTasks = getGoogleTasksByCategory(categoryId)
            compared = compareGoogleResponses(formerTasks, currentTasks)

            # Determine what to add to changes.
            if compared[0]:
                differences['newTasks'][categoryId] = compared[0]
            if compared[1]:
                differences['changedTasks'][categoryId] = compared[1]
            if compared[2]:
                differences['deletedTasks'][categoryId] = compared[2]

            currentState['tasks'][categoryId] = currentTasks

        # Changing former, serialized state to current, serialized state.
        with open('formerState.json', 'w') as json_file:
            json.dump(currentState, json_file)
            json_file.close()

        with open('changes.json', 'w') as changes_file:
            json.dump(differences, changes_file)
            changes_file.close()

        return differences


    def updateDBCategories(categoryDifferences):
        """
        Change up category entries in the database with this method.
        """
        for categoryDiff in categoryDifferences:
            obj = InboxCategories.objects.filter(id=categoryDiff['id'])
            if obj:
                for attributeDiff in categoryDiff['id']:
                    obj.update(attributeDiff=categoryDiff[attributeDiff])
            else:
                InboxCategories.objects.create(id=categoryDiff['id'], category='title')


    def updateDBTasks(taskCategories):
        """
        Change up task entries in the database with this method.
        """
        for category in taskCategories:
            for taskDiff in taskCategories['category']:
                obj = InboxTask.objects.filter(id=taskDiff['id'])
                if obj:
                    for attributeDiff in taskDiff['id']:
                        obj.update(attributeDiff=taskDiff[attributeDiff])
                else:
                    InboxTask.objects.create(\
                        id=taskDiff.get('id'),
                        title=taskDiff.get('title'),
                        category=taskDiff.get('category'),
                        dueDate=taskDiff.get('due'),
                        # Fix this later?
                        eta=None,
                        assigned=self,
                        creator=self,
                    )

    # For testing purposes

    def killAllTasks(self):
        service = self.getCredentials()
        categories = self.getGoogleTaskCategories()
        for category in categories['items']:
            if category['id'] == 'MTE1MDM3NzQyODQwOTY0NTg4MzU6MDow':
                continue
            service.tasklists().delete(tasklist=category['id']).execute()

g = GoogleTaskActions()
actions = [
    {
        'id': 12345,
        'title': 'I am child #1',
        'description': 'Feed me please',
        'dueDate': '2019-06-28T00:00:00.000Z',
    },
    {
        'id': 1234567890,
        'title': 'I am child #2',
        'description': 'Feed me plz',
        'dueDate': '2019-06-28T00:00:00.000Z',
        'estimatedDuration': 30,
    },
    {
        'id': 987654321,
        'title': 'I am child #3',
        'description': 'Feed me pls',
        'dueDate': '2019-06-28T00:00:00.000Z',
        'estimatedDuration': 10,
    },
]
g.createGoogleTask("I am the parent.", "My children will follow.", "Family", "2019-06-27T00:00:00.000Z", 30, actions=actions)
# # Testing
# CATEGORIES = {}

# from pprint import PrettyPrinter as pp
# pp = pp(indent=4)
# pprint = pp.pprint

# # 1. getGoogleTaskCategories
# categories = getGoogleTaskCategories()

# # 2. createGoogleTask
# category = createGoogleTaskCategory('Urgent')
# assert category['title'] == 'Urgent'
# CATEGORIES['Urgent'] = category['id']

# # 3. getGoogleTaskListById
# assert category == getGoogleTaskListById(category['id'])

# # 4. createGoogleTask
# task = createGoogleTask('Get the coffee', 'Only Philz please', CATEGORIES['Urgent'], '2019-06-26T00:00:00.000Z', 10, [])
# task = task['Parent']
# assert task['title'] == 'Get the coffee'
# assert task['notes'] == 'Only Philz please'

# # 5. getGoogleTaskByTaskListAndId
# assert task == getGoogleTaskByTaskListAndId(category['id'], task['id'])

# # 6. getGoogleTasksByCategory
# # assert category['id'] == getGoogleTasksByCategory(CATEGORIES['Urgent'])['id']

# # 7. completeGoogleTask
# assert task['status'] == 'needsAction'
# completeGoogleTask(task['id'], category['id'])
# task = getGoogleTaskByTaskListAndId(category['id'], task['id'])
# assert task['status'] == 'completed'

# # 8. uncompleteGoogleTask
# assert task['status'] == 'completed'
# uncompleteGoogleTask(task['id'], category['id'])
# task = getGoogleTaskByTaskListAndId(category['id'], task['id'])
# assert task['status'] == 'needsAction'

# # 9. modifyGoogleTask
# modifyGoogleTask(task['id'], 'No more coffee!', 'You got me a mocha-- I wanted a LATTE.', category=category['id'], dueDate='2019-06-27T00:00:00.000Z')

# # 10. determineChangesFromTasks
# changes = determineChangesFromTasks()
        
# # while True:
# #     changes = determineChangesFromTasks()
# #     updateDBCategories(changes['categories'])
# #     updateDBTasks(changes['tasks'])