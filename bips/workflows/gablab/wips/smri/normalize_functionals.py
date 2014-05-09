import os
from ..scripts.smri_base import get_post_struct_norm_workflow
from ..scripts.smri_utils import warp_segments
from ....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits
from glob import glob
from ....flexible_datagrabber import Data, DataBase
from bips.workflows.base import BaseWorkflowConfig

"""
Part 1: MetaWorkflow
"""

desc = """
Normalize Data to a Template (functional only)
==============================================

"""
mwf = MetaWorkflow()
mwf.uuid = '3a2e211eab1f11e19fab0019b9f22493'
mwf.tags = ['ants', 'normalize', 'warp']
mwf.help = desc

"""
Part 2: Config
"""
class config(BaseWorkflowConfig):
    uuid = traits.Str(desc="UUID")

    # Directories
    base_dir = Directory(os.path.abspath('.'),mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")

    # Subjects

    datagrabber = traits.Instance(Data, ())

    #Normalization
    norm_template = traits.File(mandatory=True,desc='Template to warp to')
    use_nearest = traits.Bool(False,desc="use nearest neighbor interpolation")
    do_segment = traits.Bool(True)
    surf_dir = traits.Directory()
    moving_images_4D = traits.Bool(True, usedefault=True, desc="True if your moving image inputs \
are time series images, False if they are 3-dimensional")
    original_res = traits.Bool(True, usedefault=True, desc="Keep the original resolution of the normalized files. \
Helps to save space. Note that isotropic resolution will be used (for example 3x3x4 will be resliced to 3x3x3).")
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()
    save_script_only = traits.Bool(False)
    # Buttons
    check_func_datagrabber = Button("Check")

    def _check_func_datagrabber_fired(self):
        subs = self.subjects
        template = [self.inputs_template,
                    self.meanfunc_template,
                    self.fsl_mat_template,
                    self.unwarped_brain_template,
                    self.affine_transformation_template,
                    self.warp_field_template]
        for s in subs:
            for t in template:
                try:
                    temp = glob(os.path.join(self.base_dir,t%s))
                except TypeError:
                    temp = []
                    for f in self.fwhm:
                        temp.append(glob(os.path.join(self.base_dir,t%(s,f))))
                print temp


def create_config():
    c = config()
    c.uuid = mwf.uuid
    
    c.datagrabber = Data(['inputs',
                          'meanfunc',
                          'fsl_mat',
                          'warp_field',
                          'unwarped_brain',
                          'affine_transformation'])
    c.datagrabber.fields = []
    subs = DataBase()
    subs.name = 'subject_id'
    subs.values = ['sub01','sub02','sub03']
    subs.iterable = True
    fwhm = DataBase()
    fwhm.name='fwhm'
    fwhm.values=['0','6.0']
    fwhm.iterable = True
    
    c.datagrabber.fields.append(subs)
    c.datagrabber.fields.append(fwhm)
    
    c.datagrabber.field_template = dict(inputs='%s/preproc/output/fwhm_%s/*.nii.gz',
                                meanfunc='%s/preproc/mean/*_mean.nii.gz',
                                fsl_mat='%s/preproc/bbreg/*.mat',
                                warp_field = '%s/smri/warped_field/*.nii*',
                                unwarped_brain='%s/smri/unwarped_brain/*.nii*',
                                affine_transformation='%s/smri/affine_transformation/*.txt')
                                
    c.datagrabber.template_args = dict(inputs=[['subject_id', 'fwhm']],
                                           meanfunc=[['subject_id']],
                                           fsl_mat=[['subject_id']],
                                           warp_field=[['subject_id']],
                                           unwarped_brain=[['subject_id']],
                                           affine_transformation=[['subject_id']])
    
    return c

mwf.config_ui = create_config

"""
Part 3: View
"""

def create_view():
    from traitsui.api import View, Item, Group
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
                      Item(name='sink_dir'),
                      Item(name='crash_dir'),
                      label='Directories', show_border=True),
                Group(Item(name='run_using_plugin',enabled_when='save_script_only'),Item('save_script_only'),
                      Item(name='plugin', enabled_when="run_using_plugin"),
                      Item(name='plugin_args', enabled_when="run_using_plugin"),
                      Item(name='test_mode'),Item('timeout'),
                      label='Execution Options', show_border=True),
                Group(Item(name='datagrabber'),
                      label='Subjects', show_border=True),
                Group(Item(name='norm_template'),
                      Item(name="do_segment"),Item("use_nearest"),
                      Item(name="surf_dir", enabled_when="do_segment"),
                      Item(name="moving_images_4D"),
                      Item(name="original_res"),
                      label='Normalization', show_border=True),
                Group(Item(name='use_advanced_options'),
                    Item(name='advanced_script',enabled_when='use_advanced_options'),
                    label='Advanced',show_border=True),
                buttons=[OKButton, CancelButton],
                resizable=True,
                width=1050)
    return view

mwf.config_view = create_view

"""
Part 4: Construct Workflow
"""

def func_datagrabber(c, name="resting_output_datagrabber"):
    # create a node to obtain the functional images
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id',
                                                             'fwhm'],
                                                   outfields=['inputs',
                                                              'meanfunc',
                                                              'fsl_mat',
                                                              'warp_field',
                                                              'unwarped_brain',
                                                              'affine_transformation']),
                         name=name)
    datasource.inputs.base_directory = c.base_dir
    datasource.inputs.template = '*'
    datasource.inputs.field_template = dict(
                                inputs=c.inputs_template,
                                meanfunc=c.meanfunc_template,
                                fsl_mat=c.fsl_mat_template,
                                warp_field = c.warp_field_template,
                                unwarped_brain=c.unwarped_brain_template,
                                affine_transformation=c.affine_transformation_template)
    datasource.inputs.template_args = dict(inputs=[['subject_id', 'fwhm']],
                                           meanfunc=[['subject_id']],
                                           fsl_mat=[['subject_id']],
                                           warp_field=[['subject_id']],
                                           unwarped_brain=[['subject_id']],
                                           affine_transformation=[['subject_id']])
    return datasource

pickfirst = lambda x: x[0]

def getsubstitutions(subject_id):
    subs=[('_subject_id_%s'%subject_id, '')]
    for i in range(200,-1,-1):
        subs.append(('_warp_images%d'%i, ''))
    subs.append(('_fwhm','fwhm'))
    subs.append(('_apply_transforms0/',"wm/"))
    subs.append(('_apply_transforms1/',"gm/"))
    subs.append(('_apply_transforms2/',"csf/"))
    return subs


def normalize_workflow(c):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio

    norm = get_post_struct_norm_workflow(timeseries = c.moving_images_4D, 
                                         original_res = c.original_res)
    
    datagrab = c.datagrabber.create_dataflow() #func_datagrabber(c)
    #fssource = pe.Node(interface=FreeSurferSource(), name='fssource')
    #fssource.inputs.subjects_dir = c.surf_dir

    #infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
    #                     name='subject_names')
    #if c.test_mode:
    #    infosource.iterables = ('subject_id', [c.subjects[0]])
    #else:
    #    infosource.iterables = ('subject_id', c.subjects)

    #infofwhm = pe.Node(util.IdentityInterface(fields=['fwhm']),
    #                     name='fwhm')
    #infofwhm.iterables = ('fwhm', c.fwhm)
 
    infosource = datagrab.get_node('subject_id_iterable')
 
    inputspec = norm.get_node('inputspec')
  
    #norm.connect(infosource, 'subject_id', datagrab, 'subject_id')
    #norm.connect(infofwhm, 'fwhm', datagrab, 'fwhm')
    norm.connect(datagrab, 'datagrabber.fsl_mat', inputspec, 'out_fsl_file')
    norm.connect(datagrab, 'datagrabber.inputs', inputspec, 'moving_image')
    norm.connect(datagrab, 'datagrabber.meanfunc', inputspec, 'mean_func')
    norm.connect(datagrab, 'datagrabber.warp_field', inputspec, 'warp_field')
    norm.connect(datagrab, 'datagrabber.affine_transformation',
                 inputspec, 'affine_transformation')
    norm.connect(datagrab, 'datagrabber.unwarped_brain',
                 inputspec, 'unwarped_brain')
    norm.inputs.inputspec.template_file = c.norm_template
    norm.inputs.inputspec.use_nearest = c.use_nearest
    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(c.sink_dir)

    outputspec = norm.get_node('outputspec')
    norm.connect(infosource, 'subject_id', sinkd, 'container')
    norm.connect(outputspec, 'warped_image', sinkd, 'smri.warped_image')

    if c.do_segment:
        seg = warp_segments()
        norm.connect(infosource, 'subject_id', seg, 'inputspec.subject_id')
        seg.inputs.inputspec.subjects_dir = c.surf_dir
        norm.connect(datagrab, 'datagrabber.warp_field', seg, 'inputspec.warp_file')
        norm.connect(datagrab, 'datagrabber.affine_transformation', seg, "inputspec.ants_affine")
        norm.connect(inputspec, 'template_file',seg, "inputspec.warped_brain")
        norm.connect(seg,"outputspec.out_files",sinkd,"smri.segments")
        
    norm.connect(infosource,('subject_id',getsubstitutions),sinkd,'substitutions')
    return norm

mwf.workflow_function = normalize_workflow

"""
Part 5: Main
"""

def main(config_file):
    c = load_config(config_file, create_config)

    workflow = normalize_workflow(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir,'job_finished_timeout': c.timeout}}
    
    if c.test_mode:
        workflow.write_graph()
    
    if c.use_advanced_options:
        exec c.advanced_script

    from nipype.utils.filemanip import fname_presuffix
    workflow.export(fname_presuffix(config_file,'','_script_').replace('.json',''))
    if c.save_script_only:
        return 0

    if c.run_using_plugin:
        workflow.run(plugin=c.plugin, plugin_args=c.plugin_args)
    else:
        workflow.run()


mwf.workflow_main_function = main

"""
Part 6: Register
"""
register_workflow(mwf)
