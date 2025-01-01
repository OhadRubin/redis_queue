# streamlit run src/visualization/monitor_queue.py
import os
import time
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import streamlit as st
import pandas as pd
from src.redis_queue import RedisQueue,Job
from collections import Counter
st.set_page_config(layout="wide")
def main():
    st.title('Queue Monitor')
    queue = RedisQueue()
    workers_info  = queue.get_all_workers()
    if len(workers_info)>0:
        df_workers = pd.DataFrame(workers_info)
        st.subheader("Workers")
        df_dict = {}
        
        for label, status in zip(["All","Running","Finished"],
                                 ["all","started", "finished"]):
            if status == "all":
                workers_filtered = df_workers
            else:
                workers_filtered=df_workers[df_workers["status"]==status]
            if label=="Running":
                df = workers_filtered
            label = f"{label} ({len(workers_filtered)})"
            
            df_dict[label] = workers_filtered     
        # st.write('tpuint --exclude="v4-64-node-1,'+",".join([x for x in df.name.tolist() if x.startswith("v4")])+'"')
        worker_tabs = st.tabs(list(df_dict.keys()))
        for tab,(label,df) in zip(worker_tabs,df_dict.items()):
            with tab:
                st.table(df)

    all_jobs = queue.get_all_jobs()
    with st.sidebar:
        st.subheader("Jobs")
        status_counts = Counter([job.status for job in all_jobs])
        statuses = ["queued", "started", "finished", "failed"]
        job_labels = []
        for label,status in zip(["Queued", "Running", "Finished", "Failed"], statuses):
            job_labels.append(f"{label} ({status_counts[status]})")
        job_tabs = st.tabs(job_labels)
        for tab, status in zip(job_tabs, statuses):
            with tab:
                jobs_filtered = [job for job in all_jobs if job.status == status]
                df_jobs = pd.DataFrame([job.__dict__ for job in jobs_filtered])
                st.table(df_jobs)
    # time.sleep(10)
    # st.experimental_rerun()


if __name__ == "__main__":
    main()
