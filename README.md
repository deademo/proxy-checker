# Proxy checker

### How to run?

To run proxy checker you can use docker image deademo/proxy_checker

Just run `docker run deademo/proxy_checker`

##### Check your proxies
To check your proxies just put them after, like this:

`docker run deademo/proxy_checker http://10.11.12.13:7654 http://anotherproxy.com:7653 someproxy.net`

Hint - you can check your proxies from local file:

`docker run deademo/proxy_checker $(cat /path/to/file/with/proxies.txt)`


##### Progress bar
You can enable progress bar by using -pb or --progress_bar argument, example:

`docker run deademo/proxy_checker -pb`

or 

`docker run deademo/proxy_checker -pb http://10.11.12.13:7654 http://anotherproxy.com:7653 someproxy.net`

##### Other argument
For other arguments use --help argument


### FAQ

##### Can i change checks applied to proxies?
No, you can not. Right now there no ease-to-use way to change checks.
