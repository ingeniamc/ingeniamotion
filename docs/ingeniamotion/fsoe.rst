FSoE
======

.. toctree::
   :maxdepth: 4

   fsoe_master/handler
   fsoe_master/maps_validator
   fsoe_master/parameters
   fsoe_master/process_image
   fsoe_master/safety_functions

FSoE PDO Participation
----------------------

When ``configure_pdos`` or ``start_master`` is called with ``start_pdos=True``, PDO exchange is
started once per EtherCAT network used by the registered FSoE handlers. Only the servo aliases
with registered FSoE handlers participate in that exchange.

Each network can have only one active PDO configuration. Stop an existing exchange before
starting FSoE PDOs if it uses a different participant group or timing configuration.

Calling ``stop_master(stop_pdos=True)`` stops PDO exchange on every network used by the registered
FSoE handlers. This stops the entire PDO exchange on those networks, not only the safety PDO
updates.

.. automodule:: ingeniamotion.fsoe
   :members:
