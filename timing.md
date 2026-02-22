# Testing the best amount of threads to use
### Sample Set:
- 45 images, 15 brackets
### Hardware used:
- CPU: AMD Ryzen 7 5700X3d
- RAM: 48Gb@3200MHz
- Storage: 1tb M.2 Gen 4 SSD
- GPU: NVIDIA RTX 3080 12GB


### 4 threads

Total time: 131.8 seconds (2.2 minutes)
Alignment: No
Images per bracket: 3 (43.9 seconds per bracket)
Total brackets processed: 25
Threads used: 4

### 6 threads (default)

Total time: 119.0 seconds (2.0 minutes)
Alignment: No
Images per bracket: 3 (39.7 seconds per bracket)
Total brackets processed: 25
Threads used: 6

### 8 threads

Total time: 117.5 seconds (2.0 minutes)
Alignment: No
Images per bracket: 3 (39.2 seconds per bracket)
Total brackets processed: 25
Threads used: 8

### 12 threads

Total time: 110.9 seconds (1.8 minutes)
Alignment: No
Images per bracket: 3 (37.0 seconds per bracket)
Total brackets processed: 25
Threads used: 12

### 16 threads

Total time: 109.8 seconds (1.8 minutes)
Alignment: No
Images per bracket: 3 (36.6 seconds per bracket)
Total brackets processed: 25
Threads used: 16