# DECODE_Cloud_UserAPI

Code for the user-facing API for DECODE OpenCloud.  
The user-facing API handles communication with the users, that can upload files (data or configuration), start jobs, check job status, and download the job outputs.  


## Endpoints
\#ToDo: endpoints description.


## Run locally
1. Copy the `.env.example` file to a `.env` file to the root of the directory.
2. Define the fields appropriately:
    - Deployment settings:
      - `PROD`: whether the app is being used in production. At this time, this only enables user and token creation points for easier setup for testing.
    - Data settings:
      - `FILESYSTEM`: one of `local` or `s3`, where the data is stored.
      - `S3_BUCKET`: if `FILESYSTEM==s3`, in what bucket the data is stored.
      - `USER_DATA_ROOT_PATH`: if `FILESYSTEM==local`, in what folder the data is stored. Relative paths can be used, but will only work with the worker-facing API if they start with `..` and the two repositories are in the same folder.
      - `DATABASE_URL`: url of the database, e.g. `sqlite:///./sql_app.db`.
      - `DATABASE_SECRET`: secret to connect to the database, will be filled into the `DATABASE_URL` in place of a `{}` placeholder. Can also be an AWS SecretsManager secret.
    - Worker-facing API:
      - `WORKERFACING_API_URL`: url to use to connect to the worker-facing API.
      - `INTERNAL_API_KEY_SECRET`: secret to authenticate to the worker-facing API, and for the worker-facing API to connect to this API, for internal endpoints. Can also be an AWS SecretsManager secret.
    - Authentication (at the moment, only AWS Cognito is supported):
      - `COGNITO_CLIENT_ID`: Cognito client ID.
      - `COGNITO_USER_POOL_ID`: Cognito user pool ID.
      - `COGNITO_REGION`: Region for the user pool.
      - `COGNITO_SECRET`: Secret for the client. Can also be an AWS SecretsManager secret.
3. Start the user-facing API with `uvicorn api.main:app --reload`.
