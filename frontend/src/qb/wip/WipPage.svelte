<script lang="ts">
  import type { WipPageProps } from "./index.ts";

  let { title, description }: WipPageProps = $props();
</script>

<div class="qb-card">
  <h2 class="qb-wip">{title}</h2>
  <p>{description}</p>
</div>

<style>
  .qb-card {
    max-width: 40em;
  }

  h2 {
    margin-top: 0;
  }

  p {
    margin-bottom: 0;
    color: var(--text-color-lightest);
  }
</style>
