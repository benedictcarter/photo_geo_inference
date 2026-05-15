# photo\_geo\_inference



Interactive geotag inference tool. 



Claude and I built this for myself to geotag my photo library, but I thought it might be useful for others as well.


It scans your photo library, extracts metadata, and based on "time taken" builds clusters of photos in time.
It then compares these cluster where you are missing geotags to clusters that do have geotags to infer likely locations.
The GUI will show you all the relevant photos in chronological order, and you can click on the photos to see bigger version.
The thumbnails show you what the written geotag will be.
If you "write" to the cluster in question, it will apply the geotag to all untagged photos in that cluster (close enough is good enough).
I recommend setting "small" time clusters (e.g. 1min) initially, and expanding it iteratively, eg 1min, 5 min, 10 min, 30 min, 1 hr, 2 hr, 4 hr, 8 hr, 12 hr, 24 hr.



## Usage workflow



1. "Browse" to your photo library. 
2. "Scan" - this will scan all files/subdirectories
3. Look at the stats for "number of untagged photos by distance to tagged photos"
4. Put a max gap like 1min (to start with)
5. "Run Clustering"
6. "Preview clusters" - you can prev/next/click on thumbnails, scroll using your mouse wheel, and "write" (this just writes to the tagged photos in this cluster, and moves to the next".
7. Once you are comfortable with what this is doing, close the preview and "write all"
8. Then I suggest choosing a bigger max gap, rinse and repeat.



Good luck!



## Python instructions:

pip install -r requirements.txt

python -m photo\_geo.gui\_main



## Authors

* Benedict Carter #https://github.com/benedictcarter
* Claude 4.6 via Perplexity
* GPT-5 Mini via Copilot

## License

Apache 2.0 License

