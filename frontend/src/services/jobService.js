import axios from 'axios';

export default {
  async createJob(jobData) {
    return await axios.post(`/jobs`, jobData);
  },
  async getJobs(offset, limit) {
    return await axios.get(`/jobs?offset=${offset}&limit=${limit}`);
  },
  async getJobDetails(jobId) {
    return await axios.get(`/jobs/${jobId}`);
  },
  async deleteJob(jobId) {
    return await axios.delete(`/jobs/${jobId}`);
  },
  async getApplications() {
    return await axios.get(`/jobs/applications`);
  }
};
