VERSION = 0.3

default: pyxpcom_examples_$(VERSION).xpi

components/pyINTPRequest.xpt: components/pyINTPRequest.idl
	/home/toddw/src/mozilla/xulrunner-sdk-2.0/bin/xpidl -I /home/toddw/src/mozilla/xulrunner-sdk-2.0/idl -I components -o components/pyINTPRequest -m typelib components/pyINTPRequest.idl

pyxpcom_examples_$(VERSION).xpi: components/pyINTPRequest.xpt content/* locale/*/*
	zip pyxpcom_examples.jar -r content locale -x "*CVS*"
	zip pyxpcom_examples_$(VERSION).xpi LICENSE.txt install.rdf chrome.manifest pyxpcom_examples.jar -r components -x "*CVS*"
	rm pyxpcom_examples.jar
