## compress\_comics

Find all the cbz/cbr files in the current directory and subdirectories and compress all the jpg/png/gif images inside with jpeg xl.  
Output files preserve the folder structure.  
Repacks cbr into cbz.  

By default compresses with:
```
--brotli_effort 11
-e / --effort 9
-d / --distance 0 (lossless)
-E / --modular_nb_prev_channels 3 
```

Compressess as many images in parallel as there are threads.  
Because of that, it may run out of memory on bigger resolutions.  

Usage:  
`python compress_comics.py output_directory`  

Needs `zip`, `cjxl`, and `unrar` installed and in PATH.  
Needs the python-magic library
