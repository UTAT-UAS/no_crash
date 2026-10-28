<script lang="ts">
	import { onMount } from 'svelte';
	import PositionMap from '#lib/PositionMap.svelte';

	// Messages from the backend, as sent by flight_visualizer_bridge.
	type State = {
		armed: boolean | null;
		mode: string | null;
		landed: boolean | null;
		position: (number | null)[] | null;
		velocity: (number | null)[] | null;
		heading: number | null;
		core_state: string | null;
		lease_holder: string | null;
		target: (number | null)[] | null;
	};
	type Result = { id: number; ok: boolean; error: string | null };

	const commands = [
		'acquire',
		'reacquire',
		'release',
		'hold',
		'arm',
		'disarm',
		'offboard',
		'position',
		'land'
	];

	let socket: WebSocket | undefined;
	let backendConnected = $state(false);
	let bridgeConnected = $state(false);
	let vehicle: State | null = $state(null);
	let lastResult = $state('');
	let goto = $state({ x: 0, y: 0, z: -3 });
	let nextId = 1;
	// Names of commands awaiting a result, by id.
	const sent: Record<number, string> = {};

	function connect() {
		const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
		socket = new WebSocket(`${scheme}://${location.host}/ws`);
		socket.onopen = () => (backendConnected = true);
		socket.onclose = () => {
			backendConnected = false;
			bridgeConnected = false;
			setTimeout(connect, 1000);
		};
		socket.onmessage = (event) => {
			const message = JSON.parse(event.data);
			if (message.type === 'link') bridgeConnected = message.connected;
			else if (message.type === 'state') vehicle = message;
			else if (message.type === 'result') showResult(message);
		};
	}

	function showResult(result: Result) {
		const name = sent[result.id] ?? `command ${result.id}`;
		delete sent[result.id];
		lastResult = result.ok ? `${name}: ok` : `${name}: ${result.error}`;
	}

	function send(name: string, args: number[] = []) {
		if (!socket || socket.readyState !== WebSocket.OPEN) {
			lastResult = `${name}: backend not connected`;
			return;
		}
		const id = nextId++;
		sent[id] = name;
		lastResult = `${name}: sent`;
		socket.send(JSON.stringify({ id, name, args }));
	}

	function format(value: unknown): string {
		if (value === null || value === undefined) return '—';
		if (Array.isArray(value)) return value.map(format).join(', ');
		return String(value);
	}

	onMount(() => {
		connect();
		return () => {
			if (socket) {
				socket.onclose = null;
				socket.close();
			}
		};
	});
</script>

<h1>Flight visualizer</h1>

<p>
	Backend: {backendConnected ? 'connected' : 'disconnected'} · Bridge: {bridgeConnected
		? 'connected'
		: 'disconnected'}
</p>

<h2>Vehicle</h2>
{#if vehicle}
	<pre>
armed          {format(vehicle.armed)}
mode           {format(vehicle.mode)}
landed         {format(vehicle.landed)}
position (m)   {format(vehicle.position)}
velocity (m/s) {format(vehicle.velocity)}
heading (rad)  {format(vehicle.heading)}
core state     {format(vehicle.core_state)}
lease holder   {format(vehicle.lease_holder) || 'none'}
target (m)     {format(vehicle.target)}</pre>
	<PositionMap position={vehicle.position} heading={vehicle.heading} target={vehicle.target} />
{:else}
	<p>No state received.</p>
{/if}

<h2>Commands</h2>
<p>
	{#each commands as name (name)}
		<button onclick={() => send(name)}>{name}</button>
	{/each}
</p>
<p>
	goto NED x <input type="number" step="0.5" bind:value={goto.x} />
	y <input type="number" step="0.5" bind:value={goto.y} />
	z <input type="number" step="0.5" bind:value={goto.z} />
	<button onclick={() => send('goto', [goto.x, goto.y, goto.z])}>goto</button>
</p>
<p>Last command: {lastResult || '—'}</p>

<style>
	button {
		margin-right: 0.3em;
	}
	input {
		width: 5em;
	}
</style>
