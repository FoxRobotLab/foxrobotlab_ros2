import numpy as np
from sklearn.model_selection import train_test_split

# --- 1. SIMULATE YOUR DATA STRUCTURE ---
# Let's say you have 55 runs and 200 distinct location patches
NUM_RUNS = 55
NUM_LOCATIONS = 200

# unique IDs for your 55 runs
run_ids = [f"run_{i:02d}" for i in range(NUM_RUNS)]

# Create a binary matrix [55, 200] indicating which locations are in which run
# 1 if the run passes through that 2x2m patch, 0 otherwise
np.random.seed(42)  # For reproducibility
run_location_matrix = np.random.randint(0, 2, size=(NUM_RUNS, NUM_LOCATIONS))


# --- 2. GREEDY MULTI-LABEL STRATIFICATION ROUTINE ---
def stratified_run_split(run_ids, run_matrix, train_size=0.8):
    """
    Splits whole runs into train/val while balancing the 200 location classes.
    """
    train_runs = []
    val_runs = []

    # Track how many times each location has been assigned to train vs val
    train_counts = np.zeros(run_matrix.shape[1])
    val_counts = np.zeros(run_matrix.shape[1])

    # Sort runs by rarity: runs with fewer locations or rarest locations are placed first
    run_rarity = np.sum(run_matrix, axis=1)
    sorted_run_indices = np.argsort(run_rarity)

    for idx in sorted_run_indices:
        run_id = run_ids[idx]
        run_profile = run_matrix[idx]

        # Calculate current balance score if we add to train vs val
        # We want to maintain a specific ratio (e.g., 4:1 for an 80/20 split)
        expected_ratio = train_size / (1 - train_size)

        # Check which set needs these locations more urgently
        train_score = np.sum(run_profile * (train_counts == 0))
        val_score = np.sum(run_profile * (val_counts == 0))

        if train_score >= val_score * expected_ratio:
            train_runs.append(run_id)
            train_counts += run_profile
        else:
            val_runs.append(run_id)
            val_counts += run_profile

    return train_runs, val_runs


# Execute the split
train_run_list, val_run_list = stratified_run_split(
    run_ids,
    run_location_matrix,
    train_size=0.80  # 80% train, 20% validation
)

print(f"Total Runs Assigned to Training: {len(train_run_list)}")
print(f"Total Runs Assigned to Validation: {len(val_run_list)}")

# --- 3. VERIFY THE CLASS DISTRIBUTION BALANCE ---
# Ensure your rarest locations are present in both sets
train_indices = [run_ids.index(r) for r in train_run_list]
val_indices = [run_ids.index(r) for r in val_run_list]

train_loc_distribution = np.sum(run_location_matrix[train_indices], axis=0)
val_loc_distribution = np.sum(run_location_matrix[val_indices], axis=0)

# Check for unrepresented locations in validation
missing_in_val = np.where(val_loc_distribution == 0)[0]
print(f"Number of locations completely missing from Validation: {len(missing_in_val)}")
