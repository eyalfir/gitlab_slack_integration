import time
import concurrent.futures
import os
from flask import Flask, request, Response
import redis
import json
import requests

app = Flask('slack-app-gitlab-pipeline-runner')
token = os.environ['SLACK_TOKEN']
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost')
redis_client = redis.Redis.from_url(REDIS_URL)
redis_client.ping()
SECONDS_TO_WAIT_BETWEEN_POLLS = 4
ROUTE = os.getenv('ROUTE', '/')
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
    app.logger.debug(resp.json())

def post_to_slack(method, json=None, params={}):
    resp = requests.post('https://slack.com/api/' + method, params=params, json=json, headers={'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + token})
    if resp.status_code != 200:
        app.logger.warning(resp.json())

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
    if not variables:
        return None
    return {'variables': [{'key': r.split('=')[0].strip(), 'value': r.split('=')[1].strip()} for r in variables.split(':') if r.strip()]}

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
    try:
        resp.raise_for_status()
    except Exception:
        app.logger.warning('bad response from gitlab')
        app.logger.warning(resp.get_data())
        raise
    return resp

def handle_gitlab_pipeline_run(event):
    inputs = event['event']['workflow_step']['inputs']
    try:
        resp = start_pipeline(inputs)
    except Exception as e:
        app.logger.warning('pipeline execution failed...')
        if inputs['announcement'].get('value', {}).get('selected_conversation'):
            channel = inputs['announcement']['value']['selected_conversation']
            resp = requests.post('https://slack.com/api/chat.postMessage', params={'text': 'pipeline execution failed', 'token': token, 'channel': channel})
        post_to_slack('workflows.stepFailed', json={'workflow_step_execute_id': event['event']['workflow_step']['workflow_step_execute_id'], 'error': 'Unable to start pipeline. Got %s' % e})
        raise
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
    status = resp.json()['status']
    web_url = resp.json()['web_url']
    if status == 'success':
        if inputs['announcement'].get('value', {}).get('selected_conversation'):
            channel = inputs['announcement']['value']['selected_conversation']
            pipeline = inputs['display_name']['value']['value']
            requests.post('https://slack.com/api/chat.postMessage', params={'text': 'Pipeline *%s* finished successfully' % pipeline, 'token': token, 'channel': channel})
        post_to_slack('workflows.stepCompleted', json={'workflow_step_execute_id': item['event']['event']['workflow_step']['workflow_step_execute_id'], 'outputs': {'pipeline_id': pipeline_id, 'pipeline_link': item['response']['web_url']}})
        redis_client.zrem('pipelines', item_raw)
    elif status == 'failed':
        if inputs['announcement'].get('value', {}).get('selected_conversation'):
            channel = inputs['announcement']['value']['selected_conversation']
            pipeline = inputs['display_name']['value']['value']
            requests.post('https://slack.com/api/chat.postMessage', params={'text': 'Pipeline *%s* (pipeline id <%s|%s>), exited with an error.' % (pipeline, web_url, pipeline_id), 'token': token, 'channel': channel})
        post_to_slack('workflows.stepFailed', json={'workflow_step_execute_id': item['event']['event']['workflow_step']['workflow_step_execute_id'], 'error': 'Pipeline failed'})
        redis_client.zrem('pipelines', item_raw)

@app.route('/poll', methods=['POST'])
def poll():
    time_to_poll_up = time.time() - SECONDS_TO_WAIT_BETWEEN_POLLS
    items = redis_client.zrangebyscore('pipelines', min='-inf', max=time_to_poll_up)
    for item_raw in items:
        redis_client.zadd('pipelines', {item_raw: time.time()}, xx=True)
        executor.submit(handle_single_item, item_raw)
    return '', 200

@app.route(ROUTE, methods=['POST', 'GET'])
def event():
    if request.json and 'challenge' in request.json:
        return Response(request.json['challenge'], mimetype="text/plain")
    if request.is_json:
        event = request.json
    else:
        event = json.loads(request.form['payload'])
    app.logger.debug(json.dumps(event, indent=2))
    if event['type'] == 'workflow_step_edit':
        handle_workflow_step_edit(event)
    elif event['type'] == 'view_submission':
        handle_view_submission(event)
    elif event['type'] == 'event_callback':
        if event['event']['type'] == 'workflow_step_execute' and event['event']['callback_id'] == 'run_gitlab_pipeline':
            handle_gitlab_pipeline_run(event)
    return '', 200

if __name__ == '__main__':
    app.run('0.0.0.0', 4444)
