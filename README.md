# DECODE_Cloud_UserAPI

Code for the user-facing API of DECODE OpenCloud.  

The user-facing API handles communication with the users. The authenticated users can:
 * handle files
   * upload data or configuration
   * delete data
   * download job outputs
 * handle jobs
   * start jobs
   * list jobs/check job status
 * (non-production environment only) handle authentication
   * create user
   * create new login token

Behind the scenes, the API communicates with the worker-facing API of DECODE OpenCloud.
It sends the worker-facing API jobs started by users, and gets job updates from it.

## Run locally
1. Copy the `.env.example` file to a `.env` file to the root of the directory.
2. Define the fields appropriately:
    - Deployment settings:
      - `PROD`: whether the app is being used in production. Setting it to false enables user and token creation points for testing.
    - Data settings:
      - `FILESYSTEM`: one of `local` or `s3`, where the data is stored.
      - `S3_BUCKET`: if `FILESYSTEM==s3`, in what bucket the data is stored.
      - `USER_DATA_ROOT_PATH`: where (folder/base path path) the data is stored. Relative paths will only work with the worker-facing API if they start with `..` and the two repositories are in the same folder.
      - `DATABASE_URL`: url of the database (e.g. `sqlite:///./sql_app.db`).
      - `DATABASE_SECRET`: secret to connect to the database, will be filled into the `DATABASE_URL` in place of a `{}` placeholder (e.g. for PostgreSQL `postgresql://postgres:{}@url:5432/database_name`). Can also be an AWS SecretsManager secret.
    - Worker-facing API:
      - `WORKERFACING_API_URL`: url to use to connect to the worker-facing API.
      - `INTERNAL_API_KEY_SECRET`: secret to authenticate to the worker-facing API, and for the worker-facing API to connect to this API, for internal endpoints. Can also be an AWS SecretsManager secret.
    - Authentication (only AWS Cognito is supported):
      - `COGNITO_CLIENT_ID`: Cognito client ID.
      - `COGNITO_USER_POOL_ID`: Cognito user pool ID.
      - `COGNITO_REGION`: Region for the user pool.
      - `COGNITO_SECRET`: Secret for the client. Can also be an AWS SecretsManager secret.
    - (Optional) Email notifications sending (only Mailjet is supported):
      - `EMAIL_SENDER_SERVICE`: Service used to send emails (can only be `mailjet`, or empty for no email notifications).
      - `EMAIL_SENDER_ADDRESS`: Address from which emails have to be sent (API key must of course have the permissions for it).
      - `EMAIL_SENDER_API_KEY`: API key to use the email sender.
      - `EMAIL_SENDER_SECRET_KEY`: API key secret to use the email sender. Can also be an AWS secret.
3. Start the user-facing API with `uvicorn api.main:app --reload`.


## Define runnable applications
Add entries in `application_config.yaml`, like:
```
<application_i>:
  <version_1>:
    <entrypoint_1>:
      app:
        cmd: [<cmd_args>]
        env: [<allowed_env_keys>]
      handler:
        image_url: <docker_image_url>  # local workers with docker-compose
        aws_job_def: <aws_batch_job_definition_name>  # cloud workers
        image_name: <image_name>  # local workers without docker-compose (e.g. using singularity)
        image_version: <image_version>  # local workers without docker-compose (e.g. using singularity)
        files_down: {<job_data_argument>: <relative_path_in_container>}  # e.g. {config_id: config, data_ids: data, artifact_ids: artifact}
        files_up: {<job_output_data_argument>: <relative_path_in_container>}  # e.g. {log: log, artifact: model}
        aws_resources:
          hardware: {<batch_hw_argument>: <default_value>}  # e.g. {MEMORY: 8000, VCPU: 4, GPU: 1}
          timeout: <timeout_value>
    <entrypoint_2>:
      ...
    ...
  <version_2>:
    ...
  ...
```
Application code should assume that all data/outputs are mounted in `/data`, i.e., the paths specified  in `files_up` and `files_down` are relative to `/data`.
