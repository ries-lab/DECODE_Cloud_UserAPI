import axios from 'axios';

export default {
    async getFiles(path) {
        path = path || '/';
        return await axios.get(`/files/${path}?show_dirs=True&recursive=False`);
    },
    async createFolder(path) {
        return await axios.post(`/files/${path}/`);
    },
    async uploadFile(path, formData) {
        let resp = axios.post(`/files/${path}url`)
        if ('data' in resp) {
            for (let key in resp['data']) {
                formData.append(key, resp['data'][key]);
            }
        }
        return await axios.post(`/files/${path}upload`, formData, {
            headers: resp['headers']
        });
    },
    async deleteItem(path) {
        return await axios.delete(`/files/${path}`);
    },
    async renameItem(path, newPath) {
        return await axios.put(`/files/${path}`, {"path": newPath});
    }
};
