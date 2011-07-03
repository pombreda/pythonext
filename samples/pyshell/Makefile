VERSION = 0.7

default: pyshell_$(VERSION).xpi

components/pyIShell.xpt: components/pyIShell.idl
	/home/toddw/src/mozilla/xulrunner-sdk-2.0/bin/xpidl -I /home/toddw/src/mozilla/xulrunner-sdk-2.0/idl -I components -o components/pyIShell -m typelib components/pyIShell.idl

pyshell_$(VERSION).xpi: components/* content/* locale/*/* install.rdf chrome.manifest LICENSE.txt
	zip pyshell.jar -r content locale -x "*CVS*"
	zip pyshell_$(VERSION).xpi LICENSE.txt install.rdf chrome.manifest pyshell.jar -r components -x "*CVS*"
	rm pyshell.jar

