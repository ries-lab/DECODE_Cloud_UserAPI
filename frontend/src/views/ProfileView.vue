<template>
  <section>
    <h1>Your Profile</h1>
    <hr/><br/>
    <div>
      <p><strong>Email address:</strong> <span>{{ user.email }}</span></p>
      <p><strong>Groups:</strong> <span>{{ user.groups }}</span></p>
    </div>
  </section>
</template>

<script>
import { defineComponent } from 'vue';
import { mapGetters } from 'vuex';

export default defineComponent({
  name: 'Profile',
  created: function() {
    return this.$store.dispatch('viewMe');
  },
  computed: {
    ...mapGetters({user: 'stateUser' }),
  },
  methods: {},
});
</script>
