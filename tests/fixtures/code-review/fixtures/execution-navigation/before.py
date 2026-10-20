def open_record(state, run_id):
    return {"screen": "execution-detail", "run": state.runs[run_id]}
