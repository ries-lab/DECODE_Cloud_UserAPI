<template>
    <div class="job-container">
      <!-- Job Creation Form -->
      <div class="job-create-section">
        <h2>Start New Job</h2>
        <job-creation-form></job-creation-form>
      </div>
  
      <!-- Jobs List -->
      <div class="job-list-section">
        <h2>Existing Jobs</h2>
        <table>
            <thead>
                <tr>
                <th>Job Name</th>
                <th>Status</th>
                <!-- Add other headings as needed -->
                <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="job in jobs" :key="job.id">
                <td>{{ job.job_name }}</td>
                <td>{{ job.status }}</td>
                <!-- Add other job details as needed -->
                <td>
                    <button @click="getJobDetails(job.id)">Details</button>
                    <button @click="deleteJob(job.id)">Delete</button>
                </td>
                </tr>
            </tbody>
        </table>
        <button @click="changePage(currentPage - 1)" :disabled="currentPage <= 1">Previous</button>
        <button @click="changePage(currentPage + 1)" :disabled="!canGoToNextPage">Next</button>
      </div>
  
      <!-- Job Details (Optional) -->
      <div v-if="selectedJob" class="job-details-section">
        <h2>Job Details</h2>
        <job-details-tree :data="selectedJob"></job-details-tree>
      </div>
    </div>
  </template>
  
  <script>
  import jobService from '@/services/jobService';
  import JobCreationForm from '@/components/JobCreationForm.vue';
  import JobDetailsTree from '@/components/JobDetailsTree.vue';
  
  export default {
    data() {
      return {
        jobs: [],
        selectedJob: null,
        currentPage: 1,
        limit: 20,
        canGoToNextPage: true,
      };
    },
    methods: {
      async createJob() {
      },
      async fetchJobs() {
        try {
          const offset = (this.currentPage - 1) * this.limit;
          const response = await jobService.getJobs(offset, this.limit);
          this.jobs = response.data;
          this.canGoToNextPage = this.jobs.length === this.limit;
        } catch (error) {
          console.error(error);
          // Handle error
        }
      },
      async getJobDetails(jobId) {
        try {
            const response = await jobService.getJobDetails(jobId);
            this.selectedJob = response.data;
        } catch (error) {
            console.error(error);
        }
        },
      async deleteJob(jobId) {
        try {
            await jobService.deleteJob(jobId);
            this.fetchJobs(); // Refresh the list after deletion
        } catch (error) {
            console.error(error);
            // Handle error
        }
        },
      changePage(page) {
        if (page < 1) {
          return;
        }
        this.currentPage = page;
        this.fetchJobs();
      },
    },
    components: {
      JobDetailsTree,
      JobCreationForm,
    },
    mounted() {
      this.fetchJobs();
    },
  };
  </script>

<style>
    .jobscontainer {
        margin: 50px;
    }
    .job-create-section, .job-list-section, .job-details-section {
        margin-bottom: 70px;
    }
</style>
