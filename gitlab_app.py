import time
import concurrent.futures
import os
from flask import Flask, request
import redis
import json
import requests

app = Flask('slack-app-gitlab-pipeline-runner')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost')
SECONDS_TO_WAIT_BETWEEN_POLLS = 4
executor = concurrent.futures.ThreadPoolExecutor(max_workers=int(os.getenv('POLLING_THREADS', '4')))

def handle_workflow_step_edit(event):
    pipeline_name = event['workflow_step']['inputs']['display_name']['value']['value'] if 'display_name' in event['workflow_step']['inputs'] else 'Pipeline'
    baseurl = event['workflow_step']['inputs']['baseurl']['value']['value'] if 'baseurl' in event['workflow_step']['inputs'] else 'https://gitlab.com/'
    project_id = event['workflow_step']['inputs']['project_id']['value']['value'] if 'project_id' in event['workflow_step']['inputs'] else ''
    personal_token = event['workflow_step']['inputs']['personal_token']['value']['value'] if 'personal_token' in event['workflow_step']['inputs'] else ''
    ref = event['workflow_step']['inputs']['ref']['value']['value'] if 'ref' in event['workflow_step']['inputs'] else 'master'
    variables = event['workflow_step']['inputs']['variables']['value'].get('value', '') if 'variables' in event['workflow_step']['inputs'] else ''
    announcement = event['workflow_step']['inputs']['announcement']['value'].get('selected_conversation') if 'announcement' in event['workflow_step']['inputs'] else None
    blocks = [
                    {
                            "type": "input",
                            "block_id": "display_name",
                            "element": {
                                    "initial_value": pipeline_name,
                                    "type": "plain_text_input",
                                    "action_id": "display_name",
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Pipeline display name"
                            },
                            "hint": {
                                    "type": "plain_text",
                                    "text": "This text will be used in communication with users"
                            }
                    },
                    {
                            "type": "input",
                            "block_id": "baseurl",
                            "element": {
                                    "action_id": "baseurl",
                                    "initial_value": baseurl,
                                    "type": "plain_text_input",
                                    "placeholder": {
                                            "type": "plain_text",
                                            "text": "https://gitlab.com/"
                                    }
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Gitlab base URL"
                            }
                    },
                    {
                            "type": "input",
                            "block_id": "project_id",
                            "element": {
                                    "action_id": "project_id",
                                    "initial_value": project_id,
                                    "type": "plain_text_input",
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Project ID"
                            },
                            "hint": {
                                    "type": "plain_text",
                                    "text": "You can find this in your project's homepage in Gitlab, right below the project name"
                            }
                    },
                    {
                            "type": "input",
                            "block_id": "personal_token",
                            "element": {
                                    "action_id": "personal_token",
                                    "initial_value": personal_token,
                                    "type": "plain_text_input",
                                    "placeholder": {
                                            "type": "plain_text",
                                            "text": "1111"
                                    }
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Personal access Token"
                            }
                    },
                    {
                            "type": "section",
                            "text": {
                                    "type": "mrkdwn",
                                    "text": "If you are not sure what personal access tokens are, or how to create one, read more <https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html|here>"
                            }
                    },
                    {
                            "type": "input",
                            "block_id": "ref",
                            "element": {
                                    "action_id": "ref",
                                    "initial_value": ref,
                                    "type": "plain_text_input",
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Ref"
                            }
                    },
                    {
                            "type": "input",
                            "optional": True,
                            "block_id": "variables",
                            "element": {
                                    "action_id": "variables",
                                    "initial_value": variables,
                                    "type": "plain_text_input",
                                    "placeholder": {
                                            "type": "plain_text",
                                            "text": "var1=value1:var2=value2"
                                    }
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Variables"
                            },
                            "hint": {
                                    "type": "plain_text",
                                    "text": "colon-seperated, key=value formatted variables to pass to the pipeline"
                            }
                    }
            ]

    announcement_block = \
                    {
                            "type": "input",
                            "optional": True,
                            "block_id": "announcement",
                            "element": {
                                    "action_id": "announcement",
                                    "type": "conversations_select",
                                    "placeholder": {
                                            "type": "plain_text",
                                            "text": "Select channels"
                                    }
                            },
                            "label": {
                                    "type": "plain_text",
                                    "text": "Channels to notify progress"
                            }
                    }
    if announcement:
        announcement_block['element']['initial_conversation'] = announcement
    blocks.append(announcement_block)
    payload = {
          "trigger_id": event['trigger_id'],
          "view": {
            "type": "workflow_step",
            "callback_id": "run_pipeline_gitlab_job",
            "blocks": blocks
          }
        }
    resp = requests.post('https://slack.com/api/views.open', json=payload, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json; charset=utf-8'})
    print(resp.json())

def post_to_slack(method, json=None, params={}):
    resp = requests.post('https://slack.com/api/' + method, params=params, json=json, headers={'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + token})
    if resp.status_code != 200:
        print(resp.json())

def handle_view_submission(event):
    payload = {'workflow_step_edit_id': event['workflow_step']['workflow_step_edit_id']}
    outputs = [{"name":"pipeline_id","type":"text","label":"Pipeline ID"},{"name":"pipeline_link","type":"text","label":"Pipeline Link"}]
    payload['outputs'] = outputs
    inputs = {}
    values = event['view']['state']['values']
    inputs['display_name'] = {"value": values['display_name']['display_name']}
    inputs['baseurl'] = {"value": values['baseurl']['baseurl']}
    inputs['project_id'] = {"value": values['project_id']['project_id']}
    inputs['personal_token'] = {"value": values['personal_token']['personal_token']}
    inputs['ref'] = {"value": values['ref']['ref']}
    inputs['variables'] = {"value": values['variables']['variables']}
    inputs['announcement'] = {"value": values['announcement']['announcement']}
    payload['inputs'] = inputs
    post_to_slack('workflows.updateStep', json=payload)

def format_variables_for_gitlab(variables):
    return {'variables': [{'key': r.split('=')[0], 'value': r.split('=')[1]} for r in variables.split(':')]}

def start_pipeline(inputs):
    personal_token = inputs['personal_token']['value']['value']
    baseurl = inputs['baseurl']['value']['value']
    project_id = inputs['project_id']['value']['value']
    variables = inputs['variables']['value'].get('value')
    ref = inputs['ref']['value']['value']
    url = '%s/api/v4/projects/%s/pipeline' % (baseurl.rstrip('/'), project_id)
    params = {'ref': ref}
    body = format_variables_for_gitlab(variables)
    resp = requests.post(url, headers={'private-token': personal_token}, params=params, json=body)
    resp.raise_for_status()
    return resp

def handle_gitlab_pipeline_run(event):
    inputs = event['event']['workflow_step']['inputs']
    resp = start_pipeline(inputs)
    pipeline = {
            'event': event,
            'response': resp.json()
    }
    redis_client.zadd('pipelines', {json.dumps(pipeline): time.time()})
    if inputs['announcement'].get('value', {}).get('selected_conversation'):
        channel = inputs['announcement']['value']['selected_conversation']
        pipeline = inputs['display_name']['value']['value']
        resp = requests.post('https://slack.com/api/chat.postMessage', params={'text': 'Running pipeline *%s*. Click <%s|here> for more details' % (pipeline, resp.json()['web_url']), 'token': token, 'channel': channel})

def handle_single_item(item_raw):
    item = json.loads(item_raw.decode('utf-8'))
    inputs = item['event']['event']['workflow_step']['inputs']
    pipeline_id = item['response']['id']
    personal_token = inputs['personal_token']['value']['value']
    baseurl = inputs['baseurl']['value']['value']
    project_id = inputs['project_id']['value']['value']
    variables = inputs['variables']['value'].get('value')
    ref = inputs['ref']['value']['value']
    url = '%s/api/v4/projects/%s/pipelines/%s' % (baseurl.rstrip('/'), project_id, pipeline_id)
    resp = requests.get(url, headers={'private-token': personal_token})
    if resp.json()['status'] == 'success':
        if inputs['announcement'].get('value', {}).get('selected_conversation'):
            channel = inputs['announcement']['value']['selected_conversation']
            pipeline = inputs['display_name']['value']['value']
            requests.post('https://slack.com/api/chat.postMessage', params={'text': 'Pipeline *%s* finished successfully' % pipeline, 'token': token, 'channel': channel})
        post_to_slack('workflows.stepCompleted', json={'workflow_step_execute_id': item['event']['event']['workflow_step']['workflow_step_execute_id'], 'outputs': {'pipeline_id': pipeline_id, 'pipeline_link': item['response']['web_url']}})
        redis_client.zrem('pipelines', item_raw)

@app.route('/poll', methods=['POST'])
def poll():
    while True:
        pair = next(iter(redis_client.zrange('pipelines', 0, 0, withscores=True)))
        if not pair:
            break
        item_raw, t = pair
        if time.time() - t > SECONDS_TO_WAIT_BETWEEN_POLLS:
            redis_client.zadd('pipelines', {item_raw: time.time()}, xx=True)
            executor.submit(handle_single_item, item_raw)
        else:
            break
    return '', 200

@app.route('/', methods=['POST', 'GET'])
def event():
    if request.is_json:
        event = request.json
    else:
        event = json.loads(request.form['payload'])
    print(json.dumps(event, indent=2))
    if event['type'] == 'workflow_step_edit':
        executor.submit(handle_workflow_step_edit, event)
    elif event['type'] == 'view_submission':
        executor.submit(handle_view_submission, event)
    elif event['type'] == 'event_callback':
        if event['event']['type'] == 'workflow_step_execute' and event['event']['callback_id'] == 'run_gitlab_pipeline':
            executor.submit(handle_gitlab_pipeline_run, event)
    return '', 200

if __name__ == '__main__':
    redis_client = redis.Redis.from_url(REDIS_URL)
    app.run('0.0.0.0', 4444)
