# Details for working with Python XPCOM #

Below are FAQ and troubleshooting questions for using Python XPCOM.


## XPCOM out parameters ##

Python handles XPCOM _inout_ and _out_ parameters differently to JavaScript, all out parameters will be returned through the Python return value. For example if your using the [nsIPromptService](https://developer.mozilla.org/en/nsipromptservice), your code would look like this:

```
from xpcom import components as Components
# void alertCheck(in nsIDOMWindow aParent, in wstring aDialogTitle,
#                 in wstring aText, in wstring aCheckMsg,
#                 inout boolean aCheckState);
promptSvc = Components.classes["@mozilla.org/embedcomp/prompt-service;1"]\
          .getService(Components.interfaces.nsIPromptService)
checkState = promptSvc.alertCheck(None, "Title", "Hello!",
                                  "Checkbox text", False)
assert checkState in (True, False)
```

## Notifications ##

Notifications are a great way to pass information between threads and/or an easy way to avoid having to write your own xpcom components.

### Sending Notifications ###

```
from xpcom import components as Components
from xpcom._xpcom import NS_PROXY_SYNC, NS_PROXY_ALWAYS, NS_PROXY_ASYNC, getProxyForObject

# Get the Mozilla observer service.
observerSvc = Components.classes["@mozilla.org/observer-service;1"].\
            getService(Components.interfaces.nsIObserverService)

# If your using a thread, you may want/need to send the notification
# via the main thread (this is a must if your notifying JavaScript code).
observerProxy = getProxyForObject(1,
                                  Components.interfaces.nsIObserverService,
                                  observerSvc,
                                  NS_PROXY_SYNC | NS_PROXY_ALWAYS)

# Send a notification.
observerProxy.notifyObservers(None, "dinner ready", "cookies")
```

### Receiving Notifications ###

On the javascript side you would create an observer and then subscribe to the hypothetical "dinner ready" service this way:

```
var mydinnerobserver = {
    observe : function(subject, topic, more_info) {
        if (topic =="dinner ready") {
            alert("It's dinner time!");
        }
    }
};
var observerSvc = Components.classes["@mozilla.org/observer-service;1"].
                       getService(Components.interfaces.nsIObserverService);
observerSvc.addObserver(mydinnerobserver, "dinner ready", false);
```

You can also subscribe to the notifications using Python - you'll need to create a class instance that supports the nsIObserver interface:

```
from xpcom import components as Components

class MyDinnerObserver(object):
   _com_interfaces_ = [ Components.interfaces.nsIObserver ]
   def observe(self, subject, topic, data):
       if topic == 'dinner ready':
           print("Dinner time: %r" % (data, ))

# Create a dinner observer instance.
mydinnerobserver = MyDinnerObserver()

# Get the observer service and listen for dinner messages.
observerSvc = Components.classes["@mozilla.org/observer-service;1"].\
              getService(Components.interfaces.nsIObserverService)
observerSvc.addObserver(myobserver, 'dinner ready', False)
```