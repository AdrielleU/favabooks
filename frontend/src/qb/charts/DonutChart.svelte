<!--
  qb-fork: a donut chart with a legend (amount and share); clicking a slice
  or legend row selects it.
-->
<script lang="ts">
  import { arc, type PieArcDatum, pie } from "d3-shape";

  import { money } from "../format.ts";
  import type { Slice } from "./data.ts";

  let {
    slices,
    currency,
    title,
    onselect,
  }: {
    slices: Slice[];
    currency: string;
    title: string;
    onselect?: (slice: Slice) => void;
  } = $props();

  const COLORS = [
    "#2563eb",
    "#f59e0b",
    "#10b981",
    "#ef4444",
    "#8b5cf6",
    "#94a3b8",
  ];
  const size = 180;
  let hover = $state<number | null>(null);
  let total = $derived(slices.reduce((sum, s) => sum + s.value, 0));
  let arcs = $derived(
    pie<Slice>()
      .value((s) => s.value)
      .sort(null)(slices),
  );
  const shape = arc<PieArcDatum<Slice>>()
    .innerRadius(size * 0.3)
    .outerRadius(size * 0.48)
    .padAngle(0.01);
  const color = (i: number) => COLORS[i % COLORS.length] ?? "#94a3b8";
  const share = (v: number) =>
    total ? `${Math.round((v / total) * 100).toString()}%` : "";
</script>

<div class="donut">
  <svg
    viewBox={`${(-size / 2).toString()} ${(-size / 2).toString()} ${size.toString()} ${size.toString()}`}
    width={size}
    height={size}
    role="img"
    aria-label={title}
  >
    {#each arcs as a, i (i)}
      <path
        d={shape(a) ?? ""}
        fill={color(i)}
        opacity={hover === null || hover === i ? 1 : 0.4}
        role="button"
        tabindex="0"
        aria-label={`${a.data.label}: ${money(a.data.value, currency)}`}
        onmouseenter={() => (hover = i)}
        onmouseleave={() => (hover = null)}
        onclick={() => onselect?.(a.data)}
        onkeydown={(e) => {
          if (e.key === "Enter") {
            onselect?.(a.data);
          }
        }}
      />
    {/each}
    <text class="center" text-anchor="middle" dy="-0.2em"
      >{hover === null ? "Total" : (slices[hover]?.label ?? "")}</text
    >
    <text class="center value" text-anchor="middle" dy="1.1em"
      >{money(
        hover === null ? total : (slices[hover]?.value ?? 0),
        currency,
      )}</text
    >
  </svg>
  <ul>
    {#each slices as s, i (s.label)}
      <li class:dim={hover !== null && hover !== i}>
        <button
          type="button"
          onmouseenter={() => (hover = i)}
          onmouseleave={() => (hover = null)}
          onclick={() => onselect?.(s)}
        >
          <i style:background={color(i)}></i>
          <span class="name">{s.label}</span>
          <span class="amt">{money(s.value, currency)}</span>
          <span class="pct">{share(s.value)}</span>
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  .donut {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem 1.5rem;
    align-items: center;
  }

  path {
    cursor: pointer;
    outline: none;
  }

  .center {
    font-size: 11px;
    fill: var(--qb-muted);
  }

  .center.value {
    font-size: 14px;
    font-weight: 700;
    fill: var(--text-color);
  }

  ul {
    flex: 1;
    min-width: min(100%, 14rem);
    padding: 0;
    margin: 0;
    list-style: none;
  }

  li.dim {
    opacity: 0.5;
  }

  li button {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    width: 100%;
    padding: 0.25rem 0;
    font: inherit;
    color: inherit;
    text-align: left;
    background: none;
  }

  i {
    flex: none;
    width: 0.75em;
    height: 0.75em;
    border-radius: 2px;
  }

  .name {
    flex: 1;
  }

  .amt {
    font-variant-numeric: tabular-nums;
  }

  .pct {
    width: 3em;
    color: var(--qb-muted);
    text-align: right;
  }
</style>
