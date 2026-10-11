
PREFIX = /usr/local

.PHONY: test install uninstall

test:
	python3 -m unittest discover -s tests -v


LIBDIR = $(PREFIX)/lib/kairos
LIBFILES = kairos $(shell git ls kairoslib/)
LIBFILE_TARGETS = $(addprefix $(LIBDIR)/,$(LIBFILES))

install: $(LIBFILE_TARGETS) $(PREFIX)/bin/kairos

$(LIBFILE_TARGETS): $(LIBDIR)/%: % | $(LIBDIR)/kairoslib
	cp -f --no-preserve=ownership $< $@

$(LIBDIR)/kairoslib $(PREFIX)/bin:
	mkdir -p $@

$(PREFIX)/bin/kairos: $(LIBDIR)/kairos | $(PREFIX)/bin
	ln -snf ../lib/kairos/kairos $@

uninstall:
	[ ! -e $(PREFIX)/bin/kairos ] || rm $(PREFIX)/bin/kairos
	[ ! -e $(LIBDIR) ] || rm -r $(LIBDIR)/
