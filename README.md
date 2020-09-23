# Gitlab Slack Integration

## Description

Add a "step from apps" step to execute gitlab pipelines.
This app support a single "step from app" called "Run Gitlab Pipeline". The step is configured with a gitlab personal access token, the gitlab base URL (i.e "https://gitlab.com"), the, project id, ref and variables.

## How to setup

1. Expose the docker image to an internet facing url being SSL.
2. In Slack, create a new app.
3. Make sure to enable "events", "interactivity", and enter the URL.
4. Give the app the following bot token scopes: "chat:write", "users.profile.read", "workflow.steps:execute"
5. Create a single Workflow step with the callback id = "run_gitlab_pipeline"
6. Install the app

## Configuring the docker image

| environmental variable | optional | default | description| example |
|-|-|-|-|-|
| SLACK_TOKEN | no | | The token on the app from slack | xoxb-1111111111-111111111-1fkjdsfkds | 
| REDIS_URL | no | | A connection URL to a redis instance | redis://10.0.0.10:6379 |
| ROUTE | yes | /dev | The URI that should be configured in Slack for the "event" and "interactive" event ||
| FLASK_DEBUG | yes | 0 | Set to 1 to enable debug logs ||
| WORKERS | yes | 8 | How many processes should be spawned ||
| PORT | yes | 8000 | Port to listen to ||
| POLLING_THREADS | yes | 4 | How many threads should be spawned to poll Gitlab pipeline statuses ||
