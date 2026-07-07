======================================
VAST Data VMS Collection Release Notes
======================================

.. contents:: Topics

v1.3.0
======

Release Summary
---------------

Adds identity, access management, and QoS policy modules, plus read-only ``*_info`` modules, a shared connection doc fragment, action groups, and ``clear_fields`` support.

v1.2.0
======

Release Summary
---------------

Adds data protection and snapshot management modules.

v1.1.0
======

Release Summary
---------------

Adds non-local identity provider modules and replaces the vastpy SDK dependency with a self-contained REST client.

Minor Changes
-------------

- Added debug tracing and centralized timeout support for improved troubleshooting.
- Replaced the ``vastpy`` SDK dependency with a self-contained REST client (``VastClient``).
- Stamped Galaxy version and git commit into the User-Agent header for request traceability.

v1.0.0
======

Release Summary
---------------

First public release of the VAST Data VMS Ansible Collection with 10 core modules for VAST storage management, token and username/password authentication, full idempotency, check mode, and diff mode support.
