# Changelog

## [0.5.5] - 2022-07-11
### Added
- Support monitoring/disturbance with CANopen protocol.
- Feedback tests.
- Monitoring/disturbance tests.


## [0.5.4] - 2022-03-17
### Changed
- Connection status listeners are all set to False by default.
- Function set_max_velocity no longer changes the profile velocity, instead it changes velocity.

### Added
- Support to multi-slave Ethernet, EoE and CANopen connections.
- Function connect_servo_ecat_interface_ip in communication.
- Function get_ifname_from_interface_ip in communication.
- Function get_current_loop_rate in configuration.
- Function set_profiler in configuration.
- Function set_max_profile_acceleration in configuration.
- Function set_max_profile_deceleration in configuration.
- Function set_max_profile_velocity in configuration.

### Fixed
- Commutation analysis feedback now returns the proper drive errors.

### Deprecated 
- Deprecated set_max_acceleration in configuration use set_profiler or set_max_profile_acceleration.


## [0.5.3] - 2022-02-16
### Changed
- Replaced ILerror exception with IMRegisterNotExist exception in base monitoring and disturbance.
- Moved SeverityLevel enum from base test to enums module.
- Moved disturbance_max_size_sample_size and monitoring_max_size_sample_size functions to capture.
- Read power stage frequency directly from registers.

### Added
- IMRegisterWrongAccess and IMTimeoutError exceptions.
- Ingenialink enums to enums module.
- IMTimeoutError exception to move_to_position and set_velocity functions.-

## [0.5.2] - 2021-11-23
### Added
- Compatibility with Python 3.7, 3.8 and 3.9.

### Fixed
- Fixed code autocompletion.

## [0.5.1] - 2021-11-17
### Added
- Compatibility with monitoring for Everest and Capitan 2.0.0.

### Changed
- Increase default monitoring timeout.
- Disable monitoring and disturbance have no effect if they are already disabled.

## [0.5.0] - 2021-10-15
### Added
- Compatibility with System Errors.
- Function register_exists in info module.
- Load firmware and boot_mode functions.
- Store and restore configuration functions.
- Add disconnect function.

## [0.4.1] - 2021-09-02
### Added
- Capture mcb_synchronization function.
- Add exceptions module.
- Phasing Check test.
- STO test.
- Create enable_monitoring_disturbance and 
  disable_monitoring_disturbance in Capture module.
- Create Info module.
- Add fault_reset function.
- Add Monitoring read function for forced trigger mode.
- Add Brake test.
- Add CANOpen communications.

### Changed
- MonitoringError and DisturbanceError exceptions to 
  IMMonitoringError and IMDisturbanceError.
- Functions motor_enable and motor_disable add error messages
  to raised exception.
- Add timeout param to read_monitoring_data.
- Update Commutation test.
- Update stop test functions.

### Removed
- Removed enable_monitoring from Monitoring class.
- Removed enable_disturbance from Disturbance class.

### Fixed
- Disturbance class and create_disturbance functions
  allow numpy arrays as a disturbance data.
- Fixed servo alias bug. Some functions were not allow
  with no default alias.

## [0.4.0] - 2021-06-28
### Added
- Error module.
- Homing functions.
- Servo connection and motor enabled checker.
- Add capability to map more than one register into disturbance.

### Changed
- Update ingeniamotion feedback test

## [0.3.1] - 2021-06-15
### Added
- Add disturbance functionality for all summit and custom drives.
- Implement feedback resolution reading and feedback type set and get.

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
  