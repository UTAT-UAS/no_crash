<script lang="ts">
	// Top-down map (North up, East right) and altimeter. Positions are PX4 local
	// NED metres; values outside the bounds are drawn at the edge.
	type Vector = (number | null)[] | null;

	let { position, heading, target }: { position: Vector; heading: number | null; target: Vector } =
		$props();

	const HALF_WIDTH = 10; // map spans ±10 m North and East of the origin
	const MAX_ALTITUDE = 10;
	const MAP_SIZE = 300; // px
	const ALT_HEIGHT = 300; // px
	const scale = MAP_SIZE / (2 * HALF_WIDTH);
	const gridLines = [-10, -5, 0, 5, 10];
	const altitudeTicks = [0, 2, 4, 6, 8, 10];

	const clamp = (v: number, low: number, high: number) => Math.min(high, Math.max(low, v));

	// [north, east] in metres to SVG [x, y], or null if not known.
	function mapPoint(v: Vector): [number, number] | null {
		if (!v || v[0] === null || v[1] === null) return null;
		const north = clamp(v[0], -HALF_WIDTH, HALF_WIDTH);
		const east = clamp(v[1], -HALF_WIDTH, HALF_WIDTH);
		return [(east + HALF_WIDTH) * scale, (HALF_WIDTH - north) * scale];
	}

	// Altitude (up = -down) to SVG y, or null if not known.
	function altitudeY(v: Vector): number | null {
		if (!v || v[2] === null) return null;
		return ALT_HEIGHT - (clamp(-v[2], 0, MAX_ALTITUDE) / MAX_ALTITUDE) * ALT_HEIGHT;
	}

	let drone = $derived(mapPoint(position));
	let goal = $derived(mapPoint(target));
	let droneAlt = $derived(altitudeY(position));
	let goalAlt = $derived(altitudeY(target));
</script>

<div class="views">
	<svg
		width={MAP_SIZE + 40}
		height={MAP_SIZE + 40}
		viewBox="-20 -20 {MAP_SIZE + 40} {MAP_SIZE + 40}"
		role="img"
		aria-label="Map"
	>
		<rect width={MAP_SIZE} height={MAP_SIZE} class="frame" />
		{#each gridLines as m (m)}
			<line x1={(m + HALF_WIDTH) * scale} y1="0" x2={(m + HALF_WIDTH) * scale} y2={MAP_SIZE} />
			<line x1="0" y1={(HALF_WIDTH - m) * scale} x2={MAP_SIZE} y2={(HALF_WIDTH - m) * scale} />
		{/each}
		<text x={MAP_SIZE / 2} y="-6" text-anchor="middle">N +{HALF_WIDTH} m</text>
		<text x={MAP_SIZE + 4} y={MAP_SIZE / 2 + 4}>E</text>
		{#if goal}
			<circle cx={goal[0]} cy={goal[1]} r="8" class="target" />
		{/if}
		{#if drone}
			<circle cx={drone[0]} cy={drone[1]} r="5" class="drone" />
			{#if heading !== null}
				<line
					x1={drone[0]}
					y1={drone[1]}
					x2={drone[0] + 14 * Math.sin(heading)}
					y2={drone[1] - 14 * Math.cos(heading)}
					class="heading"
				/>
			{/if}
		{/if}
	</svg>

	<svg
		width="90"
		height={ALT_HEIGHT + 40}
		viewBox="-40 -20 90 {ALT_HEIGHT + 40}"
		role="img"
		aria-label="Altimeter"
	>
		<rect width="20" height={ALT_HEIGHT} class="frame" />
		{#each altitudeTicks as m (m)}
			{@const y = ALT_HEIGHT - (m / MAX_ALTITUDE) * ALT_HEIGHT}
			<line x1="-5" y1={y} x2="0" y2={y} />
			<text x="-8" y={y + 4} text-anchor="end">{m} m</text>
		{/each}
		{#if goalAlt !== null}
			<line x1="-2" y1={goalAlt} x2="22" y2={goalAlt} class="target" />
		{/if}
		{#if droneAlt !== null}
			<circle cx="10" cy={droneAlt} r="5" class="drone" />
		{/if}
	</svg>
</div>
<p class="legend">
	<span class="drone-key">●</span> drone · <span class="target-key">○</span> target
</p>

<style>
	.views {
		display: flex;
		gap: 1em;
	}
	svg {
		font: 11px monospace;
	}
	line {
		stroke: #ccc;
	}
	.frame {
		fill: none;
		stroke: #333;
	}
	.drone {
		fill: #1f6feb;
	}
	.heading {
		stroke: #1f6feb;
		stroke-width: 2;
	}
	.target {
		fill: none;
		stroke: #d1242f;
		stroke-width: 2;
	}
	.drone-key {
		color: #1f6feb;
	}
	.target-key {
		color: #d1242f;
	}
	.legend {
		font-size: 0.9em;
	}
</style>
