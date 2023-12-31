<template>
    <form @submit.prevent="submitJob">
    <!-- Job Name and Application -->
    <div class="form-group">
        <h2>Submit New Job</h2>
        <div v-if="errorMessage" class="error-message">{{ errorMessage }}</div>
        <div>
            <label class="form-label" for="jobName">Job Name</label>
            <input type="text" id="jobName" v-model="job.job_name" />
        </div>
        <div>
            <label class="form-label">Application</label>
            <div class="sub-group">
                <label class="form-sublabel">Application</label>
                <select v-model="job.application.application" @change="fetchVersions">
                    <option v-for="(value, key) in applications" :key="key" :value="key">{{ key }}</option>
                </select>
                <label class="form-sublabel">Version</label>
                <select v-model="job.application.version" @change="fetchEntrypoints">
                    <option v-for="(value, key) in versions" :key="key" :value="key">{{ key }}</option>
                </select>
                <label class="form-sublabel">Entrypoint</label>
                <select v-model="job.application.entrypoint">
                    <option v-for="(value, key) in entrypoints" :key="key" :value="key">{{ key }}</option>
                </select>
            </div>
        </div>
    </div>

    <!-- Attributes -->
    <div class="form-group">
        <label class="form-label">Input</label>
        <div class="sub-group">
            <label class="form-sublabel">Configuration</label>
            <select v-model="job.attributes.files_down.config_id">
                <option v-for="(file, index) in configFiles" :key="index" :value="file">{{ file }}</option>
            </select>
        </div>
        <div class="sub-group" style="display: flex; align-items: center;">
            <label class="form-sublabel">Data</label>
            <b-form-select v-model="job.attributes.files_down.data_ids" :options="dataFiles" multiple style="width: 200px;"/>
        </div>
        <div class="sub-group" style="display: flex; align-items: center;">
            <label class="form-sublabel">Artifacts</label>
            <b-form-select v-model="job.attributes.files_down.artifact_ids" :options="artifactFiles" multiple style="width: 200px;"/>
        </div>
        <div class="sub-group" style="display: flex; align-items: center;">
            <label class="form-sublabel">Environment Variables</label>
            <div v-for="(item, index) in environs" :key="index">
                <label class="form-subsublabel">{{ item }}</label>
                <input type="text" :placeholder="item" v-model="job.attributes.env_vars[item]" />
            </div>
        </div>
    </div>

    <!-- Hardware Specs, Environment, Priority -->
    <div class="form-group">
        <label class="form-label">Runtime</label>
        <div class="sub-group">
            <label class="form-sublabel">Hardware Specs</label>
            <input type="number" placeholder="CPU Cores" v-model.number="job.hardware.cpu_cores" />
            <input type="number" placeholder="Memory" v-model.number="job.hardware.memory" />
            <input type="text" placeholder="GPU Model" v-model="job.hardware.gpu_model" />
            <input type="text" placeholder="GPU Architecture" v-model="job.hardware.gpu_archi" />
            <input type="number" placeholder="GPU Memory" v-model.number="job.hardware.gpu_mem" />
        </div>
        <div class="sub-group">
            <label class="form-sublabel" for="environment">Environment</label>
            <select id="environment" v-model="job.environment">
            <option disabled value="">Select environment</option>
            <option value="cloud">cloud</option>
            <option value="local">local</option>
            <option value=null>any</option>
            </select>
        </div>
        <div class="sub-group">
            <label class="form-sublabel" for="priority">Priority</label>
            <input type="number" id="priority" v-model.number="job.priority" />
        </div>
    </div>

    <!-- Submit Button -->
    <button type="submit">Submit Job</button>
    </form>
</template>

<script>
    import { BFormSelect } from 'bootstrap-vue-3';
    import jobService from '@/services/jobService';
    import fileService from '@/services/fileService';

    export default {
        data() {
            return {
                job: {
                    job_name: null,
                    environment: null,
                    priority: null,
                    application: {
                        application: null,
                        version: null,
                        entrypoint: null,
                    },
                    attributes: {
                        files_down: {
                                config_id: null,
                                data_ids: [],
                                artifact_ids: [],
                            },
                        env_vars: {},
                    },
                    hardware: {
                        cpu_cores: null,
                        memory: null,
                        gpu_model: null,
                        gpu_archi: null,
                        gpu_mem: null,
                    },
                },
                applications: {},
                versions: {},
                entrypoints: {},
                environs: {},
                configFiles: [],
                dataFiles: [],
                artifactFiles: [],
                errorMessage: null,
            };
        },
        components: {
            BFormSelect,
        },
        methods: {
            async fetchApplications() {
                const response = await jobService.getApplications();
                this.applications = response.data;
            },
            fetchVersions() {
                if (this.job.application.application != '') {
                    this.versions = this.applications[this.job.application.application]
                }
            },
            fetchEntrypoints() {
                if (this.job.application.version != '') {
                    this.entrypoints = this.versions[this.job.application.version]
                }
            },
            fetchEnvirons() {
                if (this.job.application.entrypoint != '') {
                    this.environs = this.entrypoints[this.job.application.entrypoint]['app']['env']
                }
            },
            async fetchInputFiles() {
                const response_cfg = await fileService.getFiles("config/");
                this.configFiles = response_cfg.data.map(file => file.path.replace('config/', ''));
                const response_data = await fileService.getFiles("data/");
                this.dataFiles = response_data.data.map(file => file.path.replace('data/', ''));
                const response_art = await fileService.getFiles("artifact/");
                this.artifactFiles = response_art.data.map(file => file.path.replace('artifact/', ''));
            },
            submitJob() {
                jobService.createJob(this.job)
                    .then(() => {
                        this.$router.push('/jobs');
                    })
                    .catch(error => {
                        this.errorMessage = error.response.data.detail;
                    });
            },
        },
        watch: {
            'job.application.application': function(newVal, oldVal) {
                if (newVal !== oldVal) {
                    this.fetchVersions();
                }
            },
            'job.application.version': function(newVal, oldVal) {
                if (newVal !== oldVal) {
                    this.fetchEntrypoints();
                }
            },
            'job.application.entrypoint': function(newVal, oldVal) {
                if (newVal !== oldVal) {
                    this.fetchEnvirons();
                }
            },
        },
        created() {
            this.fetchApplications();
            this.fetchInputFiles();
        },
    };
</script>

<style scoped>
.form-group {
    margin-bottom: 20px;
}
.form-label {
    margin-right: 10px;
    font-weight: bold;
}
.form-sublabel {
    margin-left: 10px;
    margin-right: 10px;
}
.form-subsublabel {
    margin-right: 10px;
    margin-left: 30px;
}
.sub-group {
    margin-left: 20px;
    margin-bottom: 10px;
}
.flex-container {
  display: flex;
  align-items: center;
}
.error-message {
  color: red;
}
</style>
