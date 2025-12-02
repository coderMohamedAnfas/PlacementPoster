# PlacementPoster
An official repo for placement poster

### Prerequisites

* Docker `https://docs.docker.com/engine/install/ubuntu/`
* Docker compose `https://docs.docker.com/compose/`
* make `https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/`

### Development setup

``` bash
	# If you are running this project for the first time after
	# Cloning, please execute this command
	make init

	# To publish the changes to dockerhub.
	# Before publishing the changes to dockerhub, make sure you have the repo access
	# For repo access contact @sudevank
	make publish

	## For further clarification run
	make help

	# Make sure you have installed all the components mentioned in the prerequisites
```

### Deployment
To do a deployment on any machine with docker installed
``` bash

	# Clone the repo
	git clone https://github.com/sudevan/PlacementPoster.git

	cd PlacementPoster

	# Cloning, please execute this command
	make deploy

	# Make sure you have installed all the components mentioned in the prerequisites
```

### Contributing 
Please contact the developer for further details
