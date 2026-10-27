"""Fixed exposure for the neutral 100,000 lux inspection sun; not original lighting."""
import unreal


def fixed_inspection_exposure(volume):
    baseline=volume.get_editor_property('settings')
    unreal.log('UR_EXPOSURE_BEFORE '+str({p:baseline.get_editor_property(p) for p in ('auto_exposure_min_brightness','auto_exposure_max_brightness','override_auto_exposure_min_brightness','override_auto_exposure_max_brightness')}))
    volume.modify()
    settings=volume.get_editor_property('settings')
    settings.set_editor_property('override_auto_exposure_min_brightness',False)
    settings.set_editor_property('override_auto_exposure_max_brightness',False)
    settings.set_editor_property('override_auto_exposure_method',True)
    settings.set_editor_property('auto_exposure_method',unreal.AutoExposureMethod.AEM_MANUAL)
    settings.set_editor_property('override_auto_exposure_apply_physical_camera_exposure',True)
    settings.set_editor_property('auto_exposure_apply_physical_camera_exposure',False)
    settings.set_editor_property('override_auto_exposure_bias',True)
    settings.set_editor_property('auto_exposure_bias',-13.0)
    volume.set_editor_property('settings',settings)
