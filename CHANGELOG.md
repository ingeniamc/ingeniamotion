# Changelog

## [0.3.0] - 2021-06-09
### Added
- Add SOEM communications as a way to connect to the drive.
- Add the possibility to use SDO read/writes when using SOEM.

## [0.2.0] - 2021-05-20
### Added
- Functions get_register and set_register.
- Functions create_poller.
- Monitoring class and create_monitoring function.
- Set and get power stage frequency and get position and velocity loop rate functions
  in configuration.

## [0.1.1] - 2021-03-18
### Added
- Connect servo via EOE and Ethernet.
- Add drive test: digital_halls_test, incremental_encoder_1_test, incremental_encoder_2_test
  and commutation.
- Brake configuration functions.
- Load and save configuration functions.
- Set max velocity and max acceleration functions.
- Motion functions: enable and disable motor, move_to_position, set_velocity,
  set_current_quadrature, set_operation_mode, target_latch, etc...
  