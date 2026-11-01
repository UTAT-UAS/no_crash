<script lang="ts">
	import { create, fromJson, toJson } from '@bufbuild/protobuf';
	import { onMount } from 'svelte';
	import PositionMap from '#lib/PositionMap.svelte';
	import {
		BackendMessageSchema,
		BridgeMessageSchema,
		CoreStateKind,
		type Result,
		type State,
		type Vector3
	} from '#lib/gen/flight_visualizer_pb.js';

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
			const data = JSON.parse(event.data);
			// The backend's own link status; everything else is a BridgeMessage.
			if ('link' in data) {
				bridgeConnected = data.link.connected;
				return;
			}
			const message = fromJson(BridgeMessageSchema, data, { ignoreUnknownFields: true }).message;
			if (message.case === 'state') vehicle = message.value;
			else if (message.case === 'result') showResult(message.value);
		};
	}

	function showResult(result: Result) {
		const name = sent[result.id] ?? `command ${result.id}`;
		delete sent[result.id];
		lastResult = result.ok ? `${name}: ok` : `${name}: ${result.error ?? 'failed'}`;
	}

	function send(name: string, args: number[] = []) {
		if (!socket || socket.readyState !== WebSocket.OPEN) {
			lastResult = `${name}: backend not connected`;
			return;
		}
		const id = nextId++;
		sent[id] = name;
		lastResult = `${name}: sent`;
		const message = create(BackendMessageSchema, {
			message: { case: 'command', value: { id, name, args } }
		});
		socket.send(JSON.stringify(toJson(BackendMessageSchema, message)));
	}

	function format(value: number | boolean | string | undefined): string {
		if (value === undefined || Number.isNaN(value)) return '—';
		if (typeof value === 'number') return value.toFixed(2);
		return String(value);
	}

	function formatVector(v: Vector3 | undefined): string {
		return v ? [v.x, v.y, v.z].map(format).join(', ') : '—';
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
position (m)   {formatVector(vehicle.position)}
velocity (m/s) {formatVector(vehicle.velocity)}
heading (rad)  {format(vehicle.heading)}
core state     {vehicle.coreState === undefined ? '—' : CoreStateKind[vehicle.coreState]}
core mode      {vehicle.simMode === undefined ? '—' : vehicle.simMode ? 'sim' : 'real'}
lease holder   {vehicle.leaseHolder === undefined ? '—' : vehicle.leaseHolder || 'none'}
target (m)     {formatVector(vehicle.target)}</pre>
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
