<!--
  qb-fork: a responsive bar and line chart over periods (months, quarters,
  years) with a hover tooltip; clicking a period selects it.
-->
<script lang="ts">
  import { scaleBand, scaleLinear } from "d3-scale";
  import { line } from "d3-shape";

  import { money, money_short } from "../format.ts";

  export interface Series {
    key: string;
    label: string;
    color: string;
    kind: "bar" | "line";
  }

  let {
    labels,
    values,
    series,
    currency,
    height = 260,
    format,
    zero = true,
    onselect,
  }: {
    labels: string[];
    /** values[series key][period index]. */
    values: Record<string, number[]>;
    series: Series[];
    currency: string;
    height?: number;
    /** Number format for axis and tooltip (default: money). */
    format?: (value: number) => string;
    /** Start the axis at zero (off: zoom in on the values, for prices). */
    zero?: boolean;
    onselect?: (index: number) => void;
  } = $props();

  let width = $state(600);
  let hover = $state<number | null>(null);
  const margin = { top: 12, right: 12, bottom: 28, left: 64 };

  let inner_w = $derived(Math.max(width - margin.left - margin.right, 10));
  let inner_h = $derived(height - margin.top - margin.bottom);
  let bars = $derived(series.filter((s) => s.kind === "bar"));
  let lines = $derived(series.filter((s) => s.kind === "line"));
  let all = $derived(series.flatMap((s) => values[s.key] ?? []));
  let y = $derived(
    scaleLinear()
      .domain(
        zero
          ? [Math.min(0, ...all), Math.max(0, ...all)]
          : [Math.min(...all) * 0.98, Math.max(...all) * 1.02],
      )
      .nice()
      .range([inner_h, 0]),
  );
  let x = $derived(
    scaleBand<number>()
      .domain(labels.map((_, i) => i))
      .range([0, inner_w])
      .padding(0.25),
  );
  let x_bar = $derived(
    scaleBand()
      .domain(bars.map((s) => s.key))
      .range([0, x.bandwidth()])
      .padding(0.1),
  );
  /** Show every n-th label so they don't overlap. */
  let step = $derived(Math.max(1, Math.ceil((labels.length * 64) / inner_w)));
  let paths = $derived(
    lines.map((s) => ({
      series: s,
      d:
        line<number>()
          .x((_, i) => (x(i) ?? 0) + x.bandwidth() / 2)
          .y((v) => y(v))(values[s.key] ?? []) ?? "",
    })),
  );
</script>

<div class="chart" bind:clientWidth={width}>
  <svg
    viewBox={`0 0 ${width.toString()} ${height.toString()}`}
    {height}
    role="img"
    aria-label={series.map((s) => s.label).join(", ")}
  >
    <g
      transform={`translate(${margin.left.toString()},${margin.top.toString()})`}
    >
      {#each y.ticks(5) as tick (tick)}
        <g transform={`translate(0,${y(tick).toString()})`}>
          <line x2={inner_w} class:zero={tick === 0} class="grid" />
          <text x="-8" dy="0.32em" text-anchor="end"
            >{format ? format(tick) : money_short(tick, currency)}</text
          >
        </g>
      {/each}
      {#each labels as label, i (i)}
        <g transform={`translate(${(x(i) ?? 0).toString()},0)`}>
          {#each bars as s (s.key)}
            {@const v = values[s.key]?.[i] ?? 0}
            <rect
              x={x_bar(s.key) ?? 0}
              y={Math.min(y(v), y(0))}
              width={x_bar.bandwidth()}
              height={Math.abs(y(v) - y(0))}
              fill={s.color}
              opacity={hover === null || hover === i ? 1 : 0.45}
              rx="2"
            />
          {/each}
          {#if i % step === 0}
            <text
              class="x"
              x={x.bandwidth() / 2}
              y={inner_h + 18}
              text-anchor="middle">{label}</text
            >
          {/if}
        </g>
      {/each}
      {#each paths as p (p.series.key)}
        <path d={p.d} fill="none" stroke={p.series.color} stroke-width="2.5" />
        {#each values[p.series.key] ?? [] as v, i (i)}
          <circle
            cx={(x(i) ?? 0) + x.bandwidth() / 2}
            cy={y(v)}
            r={hover === i ? 5 : 3.5}
            fill={p.series.color}
          />
        {/each}
      {/each}
      {#each labels as label, i (i)}
        <rect
          class="hit"
          x={(x(i) ?? 0) - (x.step() - x.bandwidth()) / 2}
          y="0"
          width={x.step()}
          height={inner_h}
          role="button"
          tabindex="0"
          aria-label={label}
          onmouseenter={() => (hover = i)}
          onmouseleave={() => (hover = null)}
          onfocus={() => (hover = i)}
          onblur={() => (hover = null)}
          onclick={() => onselect?.(i)}
          onkeydown={(e) => {
            if (e.key === "Enter") {
              onselect?.(i);
            }
          }}
        />
      {/each}
    </g>
  </svg>
  {#if hover !== null}
    {@const at = hover}
    {@const left = margin.left + (x(at) ?? 0) + x.bandwidth() / 2}
    <div
      class="tooltip"
      style:left={`${Math.min(Math.max(left, 90), width - 90).toString()}px`}
    >
      <strong>{labels[at]}</strong>
      {#each series as s (s.key)}
        <span
          ><i style:background={s.color}></i>{s.label}: {format
            ? format(values[s.key]?.[at] ?? 0)
            : money(values[s.key]?.[at] ?? 0, currency)}</span
        >
      {/each}
      {#if onselect}<em>Click to see this period</em>{/if}
    </div>
  {/if}
  <div class="legend">
    {#each series as s (s.key)}
      <span><i style:background={s.color}></i>{s.label}</span>
    {/each}
  </div>
</div>

<style>
  .chart {
    position: relative;
    width: 100%;
  }

  svg {
    display: block;
    width: 100%;
    overflow: visible;
  }

  text {
    font-size: 11px;
    fill: var(--qb-muted);
  }

  .grid {
    stroke: var(--border);
  }

  .grid.zero {
    stroke: var(--border-darker);
  }

  .hit {
    cursor: pointer;
    outline: none;
    fill: transparent;
  }

  .tooltip {
    position: absolute;
    top: 0;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.5rem 0.7rem;
    font-size: 0.85em;
    white-space: nowrap;
    pointer-events: none;
    background: var(--qb-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 4px 14px rgb(0 0 0 / 12%);
    transform: translateX(-50%);
  }

  .tooltip em {
    font-size: 0.85em;
    color: var(--qb-muted);
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1rem;
    justify-content: center;
    font-size: 0.85em;
    color: var(--text-color-lighter);
  }

  i {
    display: inline-block;
    width: 0.7em;
    height: 0.7em;
    margin-right: 0.35em;
    border-radius: 2px;
  }
</style>
