# OpenTrain Roadmap

OpenTrain's MVP proves the core loop: volunteer machines can be turned into a real distributed ML compute network. A user submits a dataset, workers process it in parallel, results come back merged and ready to use. That works today.

But the bigger vision is more ambitious — a world where running large ML workloads doesn't require expensive cloud infrastructure or access to powerful hardware. Where idle compute on anyone's machine can be pooled, coordinated, and put to meaningful use. This roadmap is the path from the MVP to that vision.

Items are ordered by how close they are to the current codebase. Near-term means a contributor could ship it in a weekend. Long-term means it changes the fundamental nature of what OpenTrain is.

---

## Near-Term — Making the Network More Useful

These are the features that most directly expand what users can do and what volunteers can contribute.

**GPU-aware scheduling**
Right now the coordinator assigns tasks to workers uniformly, with no knowledge of what hardware they're running. Workers should report their capabilities at registration — whether they have a CUDA-capable GPU, how much VRAM, how many CPU cores. The coordinator can then route heavy embedding and inference tasks to GPU workers and lighter preprocessing tasks to CPU-only machines. This alone could make jobs 10–100x faster for users with GPU volunteers in their network.

**More workload types**
The task registry in `worker/ml_tasks.py` is designed to be extended. High-value additions:
- `batch_inference` — run any HuggingFace model on a text shard, configurable per job
- `dataset_filter` — filter dataset rows against a condition
- `named_entity_recognition` — NER tagging via spaCy or transformers
- `chunk_embed` — embedding with a user-specified model name rather than the hardcoded default

Each of these is ~10 lines of Python. The bottleneck is deciding which ones to prioritize.

**Worker reputation system**
Volunteers are not all equal. Some machines are fast and reliable; others are slow or drop tasks. The coordinator should track completion rate, average task duration, and failure rate per worker, and use this to prefer reliable workers when assigning tasks. This also gives the dashboard a richer view of the network — not just who's connected, but who's actually contributing.

**Token-based authentication**
Currently any machine that can reach the coordinator can register as a worker and any client can submit jobs. For a public deployment this needs to change. The dashboard should be able to generate join tokens; workers must present a valid token at registration. Job submission should require an API key. This is the minimum viable security model for a shared public network.

---

## Medium-Term — Making the Network More Scalable

These items become important as the number of users, workers, and concurrent jobs grows beyond what the MVP was designed for.

**Dataset connectors**

Users should be able to point OpenTrain at a dataset reference and have the coordinator pull it directly:
- HuggingFace Hub (`datasets.load_dataset('squad')`)
- S3 or GCS bucket paths
- Any public URL

This removes the upload size limitation and makes it practical to run jobs on datasets too large to paste into a browser.

**WebSocket streaming**
The dashboard currently polls the coordinator every 2–3 seconds for job and worker status. This is fine at small scale but creates unnecessary load as the number of concurrent jobs and users grows. Replacing polling with a WebSocket connection means the coordinator pushes task completion events to the dashboard in real time — lower latency, less load, and a better user experience.

**Postgres backend**
SQLite is single-writer. At high concurrency — many workers simultaneously submitting results for the same job — this becomes a bottleneck. Swapping to Postgres is a one-line change to the SQLAlchemy connection string and unlocks proper concurrent writes, connection pooling, and the ability to run multiple coordinator replicas behind a load balancer.

**Multi-coordinator federation**
A single coordinator is a single point of failure and a geographic bottleneck. Multiple coordinator instances sharing state via Redis would allow the network to scale horizontally — more throughput, geographic distribution, and no single machine as the critical dependency.

**Worker resource reporting**
Workers should periodically report their current load — CPU %, memory pressure, available VRAM — so the coordinator can make smarter assignment decisions. Don't send a large embedding job to a machine that's already at 95% memory. Surface this data in the workers dashboard so users can see the real state of their network.

---

## Long-Term — Becoming the Volunteer ML Compute Commons

These items are further out but represent what OpenTrain could eventually become — not just a useful tool but a fundamentally new kind of infrastructure.

**Distributed model training**
The current architecture distributes *inference* workloads — running a fixed model on different data shards. The deeper goal is distributing *training* — gradient aggregation across workers, where each machine computes gradients on its data shard and the coordinator aggregates and broadcasts updated weights back. This is data-parallel distributed training, and it's the kind of workload that currently requires either expensive cloud infrastructure or a university cluster. OpenTrain could make it accessible to anyone with enough volunteers.

**Decentralized coordination**
The coordinator is currently a central server — a single point of failure and a trust requirement. A peer-to-peer coordination protocol would let workers discover each other, elect a temporary coordinator, and operate without any central infrastructure. This is technically complex but it's the difference between OpenTrain being a hosted service and OpenTrain being a protocol.

**Incentive layer**
Volunteer networks work when contributing is easy and the value is clear. An explicit credit system would make this concrete: volunteers earn credits by running workers, and spend credits by submitting jobs. This creates a self-sustaining economy where the network grows as more people want to use it — because using it requires contributing to it.

**Hosted public network**
The endgame: a permanently running public OpenTrain coordinator that anyone can submit jobs to and anyone can contribute workers to. A shared volunteer ML compute commons, like SETI@home but for useful ML workloads. The more volunteers join, the more powerful it becomes for everyone.

---

## Current Limitations to Be Aware Of

These aren't on the roadmap as features — they're honest notes about where the MVP has edges.

- **SQLite is single-writer.** At high worker concurrency, use Postgres instead (one-line change).
- **No job submission auth.** Anyone who can reach the coordinator URL can submit jobs. Fine for a private deployment, not for a public one.
- **Model loaded per worker process.** Two workers on the same machine each load their own copy of the model into memory. A shared memory model cache would fix this.
- **Results stored on local disk.** If the coordinator restarts and the volume isn't mounted, result artifacts are gone. An object store (S3, R2) would make results durable.
- **Render free tier sleeps after 15 minutes of inactivity.** First request after sleep takes 30–60 seconds. Use UptimeRobot to ping `/health` every 5 minutes to keep it warm.

---

Contributions toward any roadmap item are welcome. If you want to pick something up, open an issue first so we can align on approach — especially for the medium and long-term items where the design space is large.

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.
