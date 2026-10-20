async def open_record(state, run_id, host):
    if run_id not in state.runs:
        state.read_execution(run_id)
    source = state.sources.get(run_id)
    if source is None:
        return {"error": "Original conversation unavailable"}
    await host.load_metadata(source["thread_id"])
    return await navigate(source, host)


async def navigate(source, host):
    window = await host.resolve(source)
    metadata = await host.load_metadata(source["thread_id"])
    return {"screen": "conversation", "window": window, "metadata": metadata}
