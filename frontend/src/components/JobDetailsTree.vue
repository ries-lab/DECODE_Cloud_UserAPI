<template>
  <div v-if="isObject(data)" class="tree-node">
    <div v-for="(value, key) in data" :key="key" class="tree-item">
      <!-- Check if value is an object to decide on recursive rendering -->
      <div v-if="isObject(value)" @click="toggle(key)" class="tree-item-label">
        <span class="toggle-icon">{{ isExpanded(key) ? '-' : '+' }}</span>
        <strong>{{ key }}:</strong>
      </div>
      <div v-else class="tree-item-row">
        <strong>{{ key }}:</strong>
        <div class="tree-item-value">{{ value }}</div>
      </div>
      <!-- Recursive call for object values -->
      <div v-if="isObject(value) && isExpanded(key)" class="tree-item-content">
        <job-details-tree :data="value"></job-details-tree>
      </div>
    </div>
  </div>
</template>

<script>
  export default {
    name: "JobDetailsTree",
    props: {
      data: [Object, Array, String, Number, Boolean],
    },
    data() {
      return {
        expandedNodes: {},
      };
    },
    methods: {
      isObject(value) {
        return value && typeof value === 'object';
      },
      toggle(key) {
        this.expandedNodes[key] = !this.expandedNodes[key];
      },
      isExpanded(key) {
        return !!this.expandedNodes[key];
      },
    },
  };
</script>

<style>
  .tree-node {
    margin-left: 20px;
  }

  .tree-item {
    margin-bottom: 5px;
  }

  .tree-item-label, .tree-item-row {
    display: flex;
    align-items: center;
    cursor: pointer;
    user-select: none;
  }

  .tree-item-content {
    margin-left: 20px;
  }

  .tree-item-value {
    margin-left: 10px;
  }

  .toggle-icon {
    margin-right: 5px;
  }
</style>
