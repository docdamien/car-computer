### stop GPS service
sudo systemctl stop gps

### show status of GPS service
sudo systemctl status gps.service

### update daemon after changes
sudo systemctl daemon-reload

### update gps.service
sudo nano /lib/systemd/system/gps.service