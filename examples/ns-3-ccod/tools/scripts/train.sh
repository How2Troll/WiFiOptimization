#!/bin/bash

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 <agent> <scenario> <nWifi> <seed>"
  exit 1
fi

NS3_DIR=$YOUR_NS3_PATH #"/home/igor/ns-3-dev"
# Assuming REINFORCED_LIB is pointing to /home/igor/ns-3-dev/contrib/reinforced-lib
RLIB_DIR="${REINFORCED_LIB}/examples/ns-3-ccod"

cd "$RLIB_DIR"

AGENT=$1

if [[ $AGENT == "DDPG" ]]; then
  AGENT_TYPE="continuous"
elif [[ $AGENT == "DDQN" ]]; then
  AGENT_TYPE="discrete"
else
  echo "Invalid agent type: $AGENT"
  exit 2
fi

SCENARIO=$2
N_WIFI=$3
SEED=$4

NUM_REPS=50
MEMPOOL_KEY=1234

for (( i = 1; i <= NUM_REPS; i += 1 )); do
  if [[ $i -gt 1 ]]; then
    LOAD_PATH="$RLIB_DIR/checkpoints/${AGENT}_${SCENARIO}_${N_WIFI}_run_$(( i - 1 )).pkl.lz4"
  fi
  SAVE_PATH="$RLIB_DIR/checkpoints/${AGENT}_${SCENARIO}_${N_WIFI}_run_${i}.pkl.lz4"

  echo "Training ${AGENT} ${SCENARIO} ${N_WIFI} simulation [${i}/${NUM_REPS}]"

  export PYTHONPATH="$PYTHONPATH:/home/igor/ns-3-dev/contrib/reinforced-lib"

  python3 $RLIB_DIR/main.py --ns3Path="$NS3_DIR" --agent="$AGENT" --agentType="$AGENT_TYPE" --nWifi="$N_WIFI" --scenario="$SCENARIO" --pythonSeed="$SEED" --seed="$SEED" --loadPath="$LOAD_PATH" --savePath="$SAVE_PATH" --mempoolKey="$MEMPOOL_KEY"

  SEED=$(( SEED + 1 ))
done
