<script lang="ts">
  // qb-fork: QuickBooks-style top bar instead of ./Header.svelte, and the
  // "Add your files" popup
  import InboxHelp from "../qb/inbox/InboxHelp.svelte";
  import Header from "../qb/shell/QbHeader.svelte";
  import AsideWithButton from "./AsideWithButton.svelte";
</script>

<Header />
<AsideWithButton />
<InboxHelp />
