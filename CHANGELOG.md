# Changelog

## [Unreleased]
### Added
- FSoE module.
- STO example for Safe servo drives.
- Use only one queue in the PDO Poller to store both the timestamps and the register values.
- GPIO module.

### Fix
- Bug retrieving interface adapter name in Linux.
- The stoppable_sleep method of the wizard tests does not block the main thread.

## [0.8.1] - 2024-06-05
### Added
- Function to check if a configuration has been applied to the drive.
- Set the boot_in_app flag according to the file extension.

## [0.8.0] - 2024-04-23
### Added
- PDOs for the EtherCAT protocol.
- Register Poller using PDOs.
- Callbacks to notify exceptions in the ProcessDataThread.
- A method in the PDOPoller to subscribe to exceptions in the ProcessDataThread.
- Set the watchdog timeout of the PDO exchange.

### Changed
- The get_subnodes method from the information module now returns a dictionary with the subnodes IDs as keys and their type as values.
- Set the send_receive_processdata timeout in the ProcessDataThread according to the refresh rate.
- Cyclic parameter is defined as a RegCyclicType variable instead of a string.
- The default PDO watchdog timeout is set to 100 ms.

### Removed
- The comkit module. Now ingenialink methods are use to merge the COM-KIT and CORE dictionaries.

## [0.7.1] - 2024-03-13
### Added
- Add scan functions with info: scan_servos_ethercat_with_info and scan_servos_canopen_with_info
- Add connect_servo_virtual function

### Removed
- Support to Python 3.6 to 3.8.

## [0.7.0] - 2023-11-29
### Added
- Functions needed to load firmware to a Motion Core (MoCo).
- COM-KIT support.
- In Information class: get_product_name, get_node_id, get_ip, get_slave_id, get_name, get_communication_type, get_full_name, get_subnodes, get_categories, get_dictionary_file_name.
- In Configuration class: get_drive_info_coco_moco, get_product_code, get_revision_number, get_serial_number, get_fw_version
- no_connection marker is added for unit testing.
- Add mypy into the project.
- Add types for all functions and classes.
- Make and pass the first static type analysis.
- Function to change the baudrate of a CANopen device
- Function to get the vendor ID
- Function to change the node ID of a CANopen device
- Resolution and polarity test for DC motors (resolution test needs human check)
- Feedbacks functions to set/get feedback polarity
- Add in configuration set_velocity_pid, set_position_pid and get_rated_current
- Add functions to connect to and scan EtherCAT devices using CoE (SDOs).
- Optional backup registers for Wizard tests.
- New methods to scan the network and obtain drive info (product code and revision number).
- Method to load the FW in an ensemble of drives.

### Fixed
- check_motor_disabled decorator does not work with positional arguments
- Adapt get_encoded_image_from_dictionary for COM-KIT
- Feedback test output when symmetry and resolution errors occurred simultaneously.
- Raise exception if monitoring and disturbance features are not available.

### Changed
- Use ingenialink to get the drive's encoded image from the dictionary.
- Update subscribe and unsubscribe to network status functions.

### Deprecated 
- Support to Python 3.6 and 3.7.

## [0.6.3] - 2023-10-11
### Fixed
- Remove disturbance data before including new data.
- Set positioning mode to NO LIMITS during the feedback test.

## [0.6.2] - 2023-09-06
### Changed
- Remove EDS file path param from CANopen connection. It is no longer necessary.

### Fixed
- Fix monitoring V3. Remove rearm_monitoring from set_trigger function.

## [0.6.1] - 2023-04-03
### Added
- connect_servo_eoe_service, connect_servo_eoe_service_interface_index and connect_servo_eoe_service_interface_ip functions.

### Changed
- Removed ``boot_in_app`` argument from load_firmware_ecat and load_firmware_ecat_interface_index functions. It is not necessary anymore.

### Removed
- connect_servo_ecat, connect_servo_ecat_interface_index and connect_servo_ecat_interface_ip functions.
- get_sdo_register, get_sdo_register_complete_access and set_sdo_register functions.

### Fixed
- is_alive function in MotionController.
- subscribe_net_status and unsubscribe_net_status works for Ethernet based communication.

## [0.6.0] - 2023-01-23
### Added
- Pull request template.
- Functions get_actual_current_direct and get_actual_current_quadrature.
- Test improvements.
- Code formatting tool.

### Changed
- README image.
- Improve load_FWs script for canopen.

## [0.5.7] - 2022-12-16
### Added
- Brake tuning.

## [0.5.6] - 2022-11-10
### Fixed
- On capture.disable_disturbance, disturbance data is removed.


## [0.5.5] - 2022-07-26
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
  