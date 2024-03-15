# DECODE_Cloud_UserAPI

Code for the user-facing API of [DECODE OpenCloud](https://github.com/ries-lab/DECODE_Cloud_Documentation).  

The user-facing API handles the communication with the users.
The authenticated users can:
 * handle files
   * upload data or configuration
   * delete data
   * download job outputs
 * handle jobs
   * start jobs
   * list jobs/check job status
 * handle authentication (only in development and test environments)
   * create user
   * create new login token

Behind the scenes, the API communicates with the [worker-facing API](https://github.com/ries-lab/DECODE_Cloud_WorkerAPI) of DECODE OpenCloud.
When a user starts a job, it sends it to the [worker-facing API](https://github.com/ries-lab/DECODE_Cloud_WorkerAPI) and gets job updates from it.

## Run
#### Define the environment variables
Copy the `.env.example` file to a `.env` file at the root of the directory and define its fields appropriately:
 - Deployment settings:
   - `AUTH`: whether to activate the authentication endpoints (for testing purposes).
 - Data settings:
   - `FILESYSTEM`: one of `local` or `s3`, where the data is stored.
   - `S3_BUCKET`: if `FILESYSTEM==s3`, in what bucket the data is stored.
   - `USER_DATA_ROOT_PATH`: base path of the data storage (e.g. `../user_data` for a local filesystem, or `user_data` for S3 storage).
   - `DATABASE_URL`: url of the database (e.g. `sqlite:///./sql_app.db` for a local database, or `postgresql://postgres:{}@<db_url>:5432/<db_name>` for a PostgreSQL database on AWS RDS).
   - `DATABASE_SECRET`: secret to connect to the database, will be filled into the `DATABASE_URL` in place of a `{}` placeholder. Can also be the ARN of an AWS SecretsManager secret.
 - Worker-facing API:
   - `WORKERFACING_API_URL`: url to use to connect to the [worker-facing API](https://github.com/ries-lab/DECODE_Cloud_WorkerAPI).
   - `INTERNAL_API_KEY_SECRET`: secret to authenticate to the [worker-facing API](https://github.com/ries-lab/DECODE_Cloud_WorkerAPI), and for the [worker-facing API](https://github.com/ries-lab/DECODE_Cloud_WorkerAPI) to authenticate to this API, for internal endpoints. Can also be the ARN of an AWS SecretsManager secret.
 - Authentication (only AWS Cognito is supported):
   - `COGNITO_CLIENT_ID`: Cognito client ID.
   - `COGNITO_SECRET`: Secret for the client (if required). Can also be the ARN of an AWS SecretsManager secret.
   - `COGNITO_USER_POOL_ID`: Cognito user pool ID.
   - `COGNITO_REGION`: Region for the user pool.
 - Application config location: `APPLICATION_CONFIG_FILE` (either local path or S3 path).
 - (Optional) Email notifications sending (only Mailjet is supported):
   - `EMAIL_SENDER_SERVICE`: Service used to send emails (can only be `mailjet`, or empty for no email notifications).
   - `EMAIL_SENDER_ADDRESS`: Address from which emails have to be sent (the API key must of course have the permissions for it).
   - `EMAIL_SENDER_API_KEY`: API key to use the email sender.
   - `EMAIL_SENDER_SECRET_KEY`: API key secret to use the email sender. Can also be the ARN of an AWS SecretsManager secret.

#### Start the user-facing API
`uvicorn api.main:app --reload --port 8000`

#### View the API documentation
You can find it at `<API_URL>/docs` (if running locally, `<API_URL>=localhost:8000`).


## Add/modify runnable applications
#### Dockerize the application
See for example [DECODE](https://github.com/ries-lab/DECODE_Internal/blob/dockerfile_stable/Dockerfile) and [Comet](https://github.com/nolan1999/Comet/blob/docker/Python_interface/Dockerfile).  
The image should:
 - **Not** define an ENTRYPOINT, for technical reasons (for workers on AWS Batch, we need to prepend a command that maps the job's folder on EFS to `/files` **before** the application is started).
 - Have run-specific input parameters either defined in an input file (typically a `.yaml` configuration), or read from environment variables.
 - Save its outputs separated in an output directory, an artifact directory (an example for this would be trained ML models that will be later used for predictions, e.g. in DECODE), and a logs directory. These directories are all optional.  
Then, push the image to a public repository, e.g., using [this command line script](https://github.com/ries-lab/DECODE_AWS_Infrastructure/blob/main/scripts/push_local_dockerimage.py). 

#### Define the application configuration for DECODE OpenCloud
Add/modify entries in `application_config.yaml` (locally or on AWS S3, depending on the filesystem used), like:
```
<application_i>:
  <version_1>:
    <entrypoint_1>:
      app:
        cmd: [<cmd_args>]
        env: [<allowed_env_keys>]
      handler:
        image_url: <docker_image_url>  # local workers with docker-compose
        files_down: {<job_data_argument>: <relative_path_in_container>}  # e.g. {config_id: config, data_ids: data, artifact_ids: artifact}
        files_up: {<job_output_data_argument>: <relative_path_in_container>}  # e.g. {log: log, artifact: model, output: output}
      aws_resources:
        hardware:  # defines the resources requested to AWS if the user does not specify hardware constraints
          MEMORY: <default_memory>
          VCPU: <default_vcpu>
          GPU: <default_gpu>
        timeout: <default_timeout>
    <entrypoint_2>:
      ...
    ...
  <version_2>:
    ...
  ...
```

Example:
```
decode:
  v0_10_1:
    train:
      app:
        cmd:
          - "/docker/entrypoint.sh"
          - "--train"
          - "--calib_path=$(find /files/data -name '*.mat' | head -n 1)"
          - "--param_path=$(find /files/config -name '*.yaml' | head -n 1)"
          - "--model_path=/files/model"
          - "--log_path=/files/log"
        env: []
      handler:
        image_url: "public.ecr.aws/g0e9g3b1/decode:v0_10_1"
        files_down:
          config_id: config
          data_ids: data
          artifact_ids: artifact
        files_up:
          log: log
          artifact: model
      aws_resources:
        hardware:
          MEMORY: 8000
          VCPU: 4
          GPU: 1
        timeout: 18000
```
Note:
 - Input and output files are always mounted under `/files`.
 - `files_down` specifies where the user-provided input directories should be mounted to, within the `/files` folder. For example, the folders specified by the user as data (`data_ids`) will be mounted to `/files/data`.
 - The input files (`--calib_path` and `--param_path`) are found via the file extension. Since it is specified in `files_down` that the configuration (`config_id`) will go to `/files/config`, `$(find /files/config -name '*.yaml' | head -n 1)` picks the `.yaml` configuration from there.
 - DECODE training produces an output model, whose location is set by passing the `--model_path` argument to the Docker container (in this case, to `/files/model`). `files_up['artifact']` specifies that the worker will find the resulting artifact (the trained model) in `/files/model`.
 - In this case, there is no output data that is produced that are not logs or the output model. For this reason, there is not key `output` in `files_up`.

#### Use the new application
The new version configuration will be available immediately (the API reloads the application configuration when it is changed, see [the technical implementation here](./api/settings.py)).
