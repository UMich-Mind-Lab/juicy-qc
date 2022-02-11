# JUICY-QC #

Do you ever want to perform simple coregistration quality checks on your data, but find opening them up one-by-one in SPM or FSLeyes tiresome and slow? Do you hate the monotony of copying filepaths to google sheets for quality check tracking, then copying it all back? What about all the other problems it causes? Like

* remembering to recheck data that have been reprocessed since previous checks
* keeping up with subject lists during active data collection
* dealing with sets and sets of incredibly similar checks, and not mixing them up

Juicy-qc provides some automation for simple registration checks of MRI files. It is built using [Papaya](http://mangoviewer.com/papaya.html), a lightweight, browser-based image viewer, and python3. Multiple users can run the script at (more or less) the same time, and its logic ensures that all checks that need to happen, happen. Because check information is stored in individual files, juicy-qc output files help to ensure that qc-passing dependency checks happen between automated stages of analysis.

## HOW IT WORKS ##

### juicy-qc.py ###

#### output of juicy-qc.py -h | --help ####
usage: juicy-qc.py [-h] -d DATA_DIR -c CHECK [-n N_BATCH] [--filter FILTER [FILTER ...]] [--browser-cmd BROWSER_CMD]
                   [--config CONFIG] [--papaya-template-dir PAPAYA_TEMPLATE_DIR] [--fail | --flag | --unlock | --summary]

Perform visual quality checks on a dataset using Papaya

optional arguments:
  -h, --help            show this help message and exit
  -d DATA_DIR, --data-dir DATA_DIR
                        base path of data directory
  -c CHECK, --check CHECK
                        specify which check to perform. This must match a key in config.json.
  -n N_BATCH, --n-batch N_BATCH
                        specify how many images to include in a batch [DEFAULT = 50]
  --filter FILTER [FILTER ...]
                        argument pairs for search filter. First argument must be a field in config formatted string,
                        subsequent arguments denote possible values
  --browser-cmd BROWSER_CMD
                        specify browser command [DEFAULT = "firefox"]
  --config CONFIG       specify config file [DEFAULT = /home/burtonjz/juicy-qc/config.json]
  --papaya-template-dir PAPAYA_TEMPLATE_DIR
                        specify papaya template folder [DEFAULT = /home/burtonjz/juicy-qc/papaya_template]
  --fail                search through images that have been failed within current query
  --flag                search through images that have been flagged within current query.
  --unlock              remove lock files for current query
  --summary             output summary text for current query

*On --filter:* This command allows us to filter via a format wildcard in config.json, and then apply possible values. For example, If my current `check` uses a format fieldname `task`, and I only want to search for files matching `task` "mid" or "gng" (ignoring "nback"), then I can add the --filter task mid gng to my launch command.

This script will:
* find all files matching format strings for selected `check`
* filter files based on following criteria
  * not locked (by another instance of juicy-qc)
  * standard mode: not already done (by a `{qcDir}/{check}.done` file) and not outdated (i.e., `.done` file is not older than `overlay`)
  * fail mode: re-look at images that were previously marked fail
  * flag mode: re-look at only images that were previously marked flag
  * select first `n_batch` valid files and create a `{qcDir}/{check}.lock` file
* prepare and launch a papaya instance, which allows users to rate "PASS" "FAIL" or "FLAG", then save that data into a csv file
* retrieve output csv, save individual quality check `.done` files, remove `.lock` files

### The juicy-qc config file ###

Juicy-qc requires a JSON formatted config file, stored in this directory as "config.json", to search through a target dataset for matching files.

```json
{
  "checkname":{
    "overlay":"{data_dir}/sub-{sub}/path/to/overlay.nii.gz",
    "image":"{data_dir}/sub-{sub}/path/to/image.nii.gz",
    "qcDir":"{data_dir}/sub-{sub}/path/to/qc_directory"
  }
}
```

`overlay`, `image`, and `qcDir` allow arbitrary format strings which will be read into `juicy-qc.py` by default. The `qcDir` specifies the directory for `{check}.done` and `{check}.lock` files. All three can use completely arbitrary python3 format strings so that file searches can be dynamic to your data pipeline.

`image` and `qcDir` can *only* contain format strings matching `overlay`, though are not required to have *all* format strings present in the `overlay`. For example, see the `checkwarp` settings below:

```json
{
  "checkreg":{
    "overlay":"{data_dir}/preproc/sub-{subject}/ses-{session}/task-{task}/acq-{acq}/run-{run}/sub-{subject}_ses-{session}_task-{task}_acq-{acq}_run-{run}_boldref.nii.gz",
    "image":"{data_dir}/preproc/sub-{subject}/ses-{session}/task-{task}/acq-{acq}/run-{run}/T1w.nii.gz",
    "qcDir":"{data_dir}/preproc/sub-{subject}/ses-{session}/task-{task}/acq-{acq}/run-{run}/QC"
  },
  "checkwarp":{
    "overlay":"{data_dir}/preproc/sub-{subject}/ses-{session}/task-{task}/acq-{acq}/run-{run}/sub-{subject}_ses-{session}_task-{task}_acq-{acq}_run-{run}_wutpboldref.nii.gz",
    "image":"../../lib/spm12/canonical/avg152T1.nii",
    "qcDir":"{data_dir}/preproc/sub-{subject}/ses-{session}/task-{task}/acq-{acq}/run-{run}/QC"
  }
}
```
