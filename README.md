## compress\_comics

Find all the cbz/cbr files in the current directory and subdirectories and compress all the jpg/png/gif images inside with jpeg xl.  
Output files preserve the folder structure.  
Repacks cbr into cbz.  

By default, compresses with:
```
-d / --distance 0 (lossless)
-j / --lossless_jpeg 1
```

Compresses as many images in parallel as there are threads.  
Because of that, it may run out of memory on bigger resolutions.  
Adjust with:  
```
-t / --threads
```

Basic usage:  
`compress_comics output_directory`  

To check all program options:  
`compress_comics -h`

Needs `cjxl` installed and in PATH.  
