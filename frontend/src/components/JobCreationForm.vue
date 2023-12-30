<template>
    <form @submit.prevent="submitForm">
    <!-- Job Name -->
    <div>
        <label for="jobName">Job Name</label>
        <input type="text" id="jobName" v-model="job.job_name" />
    </div>

    <!-- Environment -->
    <div>
        <label for="environment">Environment</label>
        <select id="environment" v-model="job.environment">
        <option disabled value="">Please select one</option>
        <option value="cloud">Cloud</option>
        <option value="local">Local</option>
        <option value=null>Any</option>
        </select>
    </div>

    <!-- Priority -->
    <div>
        <label for="priority">Priority</label>
        <input type="number" id="priority" v-model.number="job.priority" />
    </div>

    <!-- Application -->
    <div>
        <label>Application</label>
        <input type="text" placeholder="Application" v-model="job.application.application" />
        <input type="text" placeholder="Version" v-model="job.application.version" />
        <input type="text" placeholder="Entrypoint" v-model="job.application.entrypoint" />
    </div>

    <!-- Attributes -->
    <div>
        <label>Attributes</label>
        <input type="text" placeholder="Config ID" v-model="job.attributes.files_down.config_id" />

        <div>
        <label>Data IDs</label>
        <div v-for="(id, index) in job.attributes.data_ids" :key="index">
            <input type="text" v-model="job.attributes.data_ids[index]" />
            <button type="button" @click="removeDataId(index)">Remove</button>
        </div>
        <button type="button" @click="addDataId">Add Data ID</button>
        </div>

        <div>
        <label>Artifact IDs</label>
        <div v-for="(id, index) in job.attributes.artifact_ids" :key="index">
            <input type="text" v-model="job.attributes.artifact_ids[index]" />
            <button type="button" @click="removeArtifactId(index)">Remove</button>
        </div>
        <button type="button" @click="addArtifactId">Add Artifact ID</button>
        </div>

        <div>
        <label>Environment Variables</label>
        <div v-for="(value, key) in job.attributes.env_vars" :key="key">
            <input type="text" :placeholder="key" v-model="job.attributes.env_vars[key]" />
            <button type="button" @click="removeEnvVar(key)">Remove</button>
        </div>
        <button type="button" @click="addEnvVar">Add Environment Variable</button>
        </div>
    </div>

    <!-- Hardware Specs -->
    <div>
        <label>Hardware Specs</label>
        <input type="number" placeholder="CPU Cores" v-model.number="job.hardware.cpu_cores" />
        <input type="number" placeholder="Memory" v-model.number="job.hardware.memory" />
        <input type="text" placeholder="GPU Model" v-model="job.hardware.gpu_model" />
        <input type="text" placeholder="GPU Architecture" v-model="job.hardware.gpu_archi" />
        <input type="number" placeholder="GPU Memory" v-model.number="job.hardware.gpu_mem" />
    </div>

    <!-- Submit Button -->
    <button type="submit">Create Job</button>
    </form>
</template>

<script>
    export default {
        data() {
        return {
            job: {
            job_name: '',
            environment: '',
            priority: null,
            application: {
                application: '',
                version: '',
                entrypoint: '',
            },
            attributes: {
                files_down: {
                config_id: '',
                },
                data_ids: [],
                artifact_ids: [],
                env_vars: {},
            },
            hardware: {
                cpu_cores: null,
                memory: null,
                gpu_model: '',
                gpu_archi: '',
                gpu_mem: null,
            },
            },
        };
        },
        methods: {
        addDataId() {
            this.job.attributes.data_ids.push('');
        },
        removeDataId(index) {
            this.job.attributes.data_ids.splice(index, 1);
        },
        addArtifactId() {
            this.job.attributes.artifact_ids.push('');
        },
        removeArtifactId(index) {
            this.job.attributes.artifact_ids.splice(index, 1);
        },
        addEnvVar() {
            // Use a unique key for new environment variables
            const newVarKey = `newVar${Object.keys(this.job.attributes.env_vars).length}`;
            this.job.attributes.env_vars = {
            ...this.job.attributes.env_vars,
            [newVarKey]: '' // Add new key with an empty value
            };
        },
        removeEnvVar(key) {
            const { [key]: omit, ...rest } = this.job.attributes.env_vars;
            this.job.attributes.env_vars = rest;
            console.log(omit);
        },
        submitForm() {
            // Handle form submission, e.g., make an API call
            console.log(this.job);
        },
        },
    };
</script>
