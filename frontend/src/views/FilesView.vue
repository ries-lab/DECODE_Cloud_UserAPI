<template>
  <h1>Files</h1>
  <div>
    <header>
      <button @click="goUp" :disabled="path === ''">Back</button>
      <input type="text" v-model="path" placeholder="Path">
      <button class="btn-flat" @click="createFolder">Add Folder</button>
      <!-- File upload input -->
      <input type="file" @change="handleFileUpload"/>
    </header>
    <main>
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Name</th>
            <th>Size</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, key) in files" :key="key" @dblclick="openAction(key, item)">
            <td>{{ item.type }}</td>
            <td>
              <input type="text" :value="item.path.replace(this.path, '')" @change="ev => renameItem(item.path, ev.target.value)">
            </td>
            <td>{{ item.type === 'directory' ? '-' : item.size + ' Bytes' }}</td>
            <td><button @click="deleteItem(item.path)">Delete</button></td>
          </tr>
        </tbody>
      </table>
    </main>
  </div>
</template>


<script>
import { defineComponent } from 'vue';
import fileService from '@/services/fileService';

export default defineComponent({
  name: 'FilesView',
  data() {
    return {
      path: '',
      files: [],
    };
  },
  methods: {
    openAction: function (name, item) {
      if (item.type === 'directory') {
          this.path = item.path;
          this.fetchFiles();
      }
    },
    fetchFiles() {
      fileService.getFiles(this.path)
        .then(response => {
          this.files = response.data;
        })
        .catch(error => {
          console.error("Error fetching files:", error);
        });
    },
    goUp() {
      let pathParts = this.path.trimEnd('/').split('/').filter(Boolean);
      pathParts.pop();
      this.path = pathParts.join('/');
      if (this.path != '') {
        this.path = this.path + '/';
      }
      this.fetchFiles();
    },
    createFolder() {
      fileService.createFolder(this.path + 'new')
        .then(() => {
          this.fetchFiles();
        });
    },
    handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        this.uploadFile(file);
      }
    },
    uploadFile(file) {
      let formData = new FormData();
      formData.append('file', file);
      fileService.uploadFile(this.path, formData)
        .then(() => {
          this.fetchFiles();
        })
        .catch(error => {
          console.error("Error uploading file:", error);
        });
    },
    deleteItem(path) {
      fileService.deleteItem(path)
        .then(() => {
          this.fetchFiles();
        });
    },
    renameItem(path, newName) {
      let newPath = this.path.trimEnd("/") + '/' + newName;
      fileService.renameItem(path, newPath)
        .then(() => {
          this.fetchFiles();
        });
    },
  },
  mounted() {
    this.fetchFiles();
  }
})
</script>
