import pandas as pd

def load_and_prepare_predicted(file_path):
    """Loads predicted data, handles potential BOM, selects, and renames columns."""
    try:
        # Explicitly specify encoding, utf-8 is common, but adjust if needed
        df = pd.read_csv(file_path, encoding='utf-8')

        # Determine the correct columns to use.
        # The predicted file ('2025-05-12T19-48_export.csv' example) had columns:
        # Unnamed, timestamp, username, message, sentiment
        # If your 'predicted_data_500.csv' directly matches this, 'usecols' can select them by name.
        # If the first column is indeed an index without a name, pandas might name it 'Unnamed: 0'.
        
        # Check if the first column is the BOM-prefixed index or 'Unnamed: 0'
        # and adjust column selection if necessary.
        # A more robust way is to check if 'message' or 'sentiment' is in the expected place.

        # Let's assume the columns are consistently named 'timestamp', 'username', 'message', 'sentiment'
        # and the first unnamed column (if present) can be ignored by `usecols` or if it's named.
        # If the predicted file *always* has the exact headers: ',timestamp,username,message,sentiment'
        # (where the first is an unnamed index), then this is okay.
        # However, the line `df = pd.read_csv(file_path, encoding='utf-8')` already reads all columns.
        # We can then select.

        # If the first column is an index and is read as '\ufeff' or 'Unnamed: 0'
        # we will select the others by name.
        required_cols_predicted = ['timestamp', 'username', 'message', 'sentiment']
        if not all(col in df.columns for col in required_cols_predicted):
            # This might happen if the first column was unnamed and shifted others,
            # or if headers are different. Let's try to adapt if a BOM-like first col exists.
            if df.columns[0].startswith('\ufeff') or df.columns[0].lower() == 'unnamed: 0':
                # Assuming the actual data columns follow the unnamed index
                # Check if the *next* set of columns matches our expectation
                if all(col in df.columns[1:] for col in required_cols_predicted):
                     df_predicted = df[required_cols_predicted].copy() # Select by name, pandas handles the original index
                else:
                    raise KeyError(f"Required columns not found even after accounting for a potential leading unnamed column. Columns found: {df.columns.tolist()}")
            else:
                 raise KeyError(f"Required columns not found. Columns found: {df.columns.tolist()}")
        else:
            df_predicted = df[required_cols_predicted].copy()


        df_predicted = df_predicted.rename(columns={'message': 'message_text',
                                                    'sentiment': 'predicted_label'})
        return df_predicted
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except KeyError as e:
        print(f"Error: A required column was not found in '{file_path}'. Missing column(s): {e}")
        # Try to read just the headers to show what was found
        try:
            headers = pd.read_csv(file_path, encoding='utf-8', nrows=0).columns.tolist()
            print(f"Columns found in the file: {headers}")
        except:
            pass
        return None
    except Exception as e:
        print(f"An error occurred while loading or preparing predicted data from '{file_path}': {e}")
        return None

def load_and_prepare_actual(file_path):
    """Loads actual labeled data, selects, and renames columns."""
    try:
        # Assuming your 'labeled_data_500.csv' looks like the `kick_chat_labeled_500.csv` structure
        # which had headers: username,content,msg_id,user_id,timestamp,label
        df_actual = pd.read_csv(file_path, encoding='utf-8',
                                usecols=['timestamp', 'username', 'content', 'label'])
        df_actual = df_actual.rename(columns={'content': 'message_text',
                                              'label': 'actual_label'})
        return df_actual
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except KeyError as e:
        print(f"Error: A required column was not found in '{file_path}'. Missing column(s): {e}")
        try:
            headers = pd.read_csv(file_path, encoding='utf-8', nrows=0).columns.tolist()
            print(f"Columns found in the file: {headers}")
        except:
            pass
        return None
    except Exception as e:
        print(f"An error occurred while loading or preparing actual data from '{file_path}': {e}")
        return None

# --- Define file paths ---
labeled_file_path = "data/labeled_data/kick_chat_labeled_500.csv"
predicted_file_path = "data/predicted_data/predicted_data_500.csv" # Or your '2025-05-12T19-48_export.csv'
print(f"predicted_file_path:  {predicted_file_path}, labeled_file_path: {labeled_file_path}")
# --- Load and prepare data ---
df_predicted = load_and_prepare_predicted(predicted_file_path)
df_actual = load_and_prepare_actual(labeled_file_path)

# --- Proceed only if both DataFrames loaded successfully ---
if df_predicted is not None and df_actual is not None:
    print(f"Predicted data loaded: {len(df_predicted)} rows.")
    print("Predicted sentiment counts:")
    print(df_predicted['predicted_label'].value_counts(dropna=False))
    print("-" * 30)

    print(f"Actual data loaded: {len(df_actual)} rows.")
    print("Actual sentiment counts:")
    print(df_actual['actual_label'].value_counts(dropna=False))
    print("-" * 30)


    # --- Clean up merge keys (optional, but good practice) ----
    merge_key_columns = ['timestamp', 'username', 'message_text']
    for col in merge_key_columns:
        if col in df_predicted.columns and df_predicted[col].dtype == 'object':
            df_predicted[col] = df_predicted[col].str.strip()
        if col in df_actual.columns and df_actual[col].dtype == 'object':
            df_actual[col] = df_actual[col].str.strip()

    # --- Merge the dataframes ---
    try:
        merged_df = pd.merge(df_predicted, df_actual,
                             on=['timestamp', 'username', 'message_text'],
                             how='inner')
    except Exception as e:
        print(f"Error during merging: {e}")
        print("Ensure that the merge key columns ('timestamp', 'username', 'message_text') exist and are compatible in both files.")
        merged_df = pd.DataFrame()

    if merged_df.empty:
        if not df_predicted.empty and not df_actual.empty:
             print("\nNo common rows found after merging. Check the merge keys and data consistency.")
             print("Merge keys used: 'timestamp', 'username', 'message_text'.")
             print("Sample predicted data for merge keys:")
             print(df_predicted[merge_key_columns].head())
             print("Sample actual data for merge keys:")
             print(df_actual[merge_key_columns].head())
    else:
        print(f"\nSuccessfully merged {len(merged_df)} common rows for comparison.")
        print("-" * 30)
        # --- Sentiment counts in the MERGED dataset ---
        print("Sentiment counts in the (merged) predicted data:")
        print(merged_df['predicted_label'].value_counts(dropna=False))
        print("\nSentiment counts in the (merged) actual data:")
        print(merged_df['actual_label'].value_counts(dropna=False))
        print("-" * 30)

        # --- Find differences ---
        # Convert labels to lowercase string for case-insensitive comparison
        # Also handle if labels could be NaN, though merge might drop them
        merged_df['predicted_label_lower'] = merged_df['predicted_label'].astype(str).str.lower()
        merged_df['actual_label_lower'] = merged_df['actual_label'].astype(str).str.lower()
        
        differences = merged_df[merged_df['predicted_label_lower'] != merged_df['actual_label_lower']]

        # --- Display the differences ---
        if not differences.empty:
            print(f"\nFound {len(differences)} differences between predicted and actual labels:")
            print("---------------------------------------------------------------------")
            print(differences[['timestamp', 'username', 'message_text', 'predicted_label', 'actual_label']])
            
            print("\nCounts of differing predictions:")
            print(differences.groupby(['actual_label', 'predicted_label']).size().reset_index(name='count'))

        else:
            print("\nNo differences found! Predicted sentiments match actual labels for all common entries.")

        print(f"\nTotal common rows compared: {len(merged_df)}")
        if len(df_predicted) != len(merged_df) or len(df_actual) != len(merged_df):
            print(f"Note: Predicted file originally had {len(df_predicted)} rows, Labeled file originally had {len(df_actual)} rows.")
            print("The comparison was done on the intersection (common rows) of these datasets based on the merge keys.")

else:
    print("\nComparison aborted due to errors in loading one or both data files.")