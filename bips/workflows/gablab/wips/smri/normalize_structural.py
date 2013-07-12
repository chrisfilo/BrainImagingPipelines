import os
from ..scripts.smri_base import get_full_norm_workflow, get_struct_norm_workflow
from ..scripts.smri_utils import warp_segments
from ....base import MetaWorkflow, load_config, register_workflow
from traits.api import HasTraits, Directory, Bool, Button
import traits.api as traits

"""
Part 1: Define a MetaWorkflow
"""

desc = """
Normalize Data to a Template
==========================================

"""
mwf = MetaWorkflow()
mwf.uuid = '21abfee68e2211e181190019b9f22493'
mwf.tags = ['ants', 'normalize', 'warp']
mwf.help = desc

"""
Part 2: Define the config class & create_config function
"""

class config(HasTraits):
    uuid = traits.Str(desc="UUID")

    # Directories
    working_dir = Directory(mandatory=True, desc="Location of the Nipype working directory")
    base_dir = Directory(os.path.abspath('.'),mandatory=True, desc='Base directory of data. (Should be subject-independent)')
    sink_dir = Directory(mandatory=True, desc="Location where the BIP will store the results")
    crash_dir = Directory(mandatory=False, desc="Location to store crash files")
    surf_dir = Directory(mandatory=True, desc="Freesurfer subjects directory")

    # Execution
    run_using_plugin = Bool(False, usedefault=True, desc="True to run pipeline with plugin, False to run serially")
    plugin = traits.Enum("PBS", "MultiProc", "SGE", "Condor", "CondorDAGMan",
                         usedefault=True,
                         desc="plugin to use, if run_using_plugin=True")
    plugin_args = traits.Dict({"qsub_args": "-q many"},
                                                      usedefault=True, desc='Plugin arguments.')
    test_mode = Bool(False, mandatory=False, usedefault=True,
                     desc='Affects whether where and if the workflow keeps its \
                            intermediary files. True to keep intermediary files. ')
    timeout = traits.Float(14.0)
    # Subjects
    subjects = traits.List(traits.Str, mandatory=True, usedefault=True,
                          desc="Subject id's. Note: These MUST match the subject id's in the \
                                Freesurfer directory. For simplicity, the subject id's should \
                                also match with the location of individual functional files.")
    fwhm=traits.List(traits.Float())
    inputs_template = traits.String('%s/preproc/output/fwhm_%s/*.nii.gz')
    meanfunc_template = traits.String('%s/preproc/mean/*_mean.nii.gz')
    fsl_mat_template = traits.String('%s/preproc/bbreg/*.mat')

    #Normalization
    norm_template = traits.File(mandatory=True,desc='Template to warp to')
    do_segment = traits.Bool(False)
    do_anatomical_only = traits.Bool(True)
    # Advanced Options
    use_advanced_options = traits.Bool()
    advanced_script = traits.Code()
    save_script_only = traits.Bool(False)
    # Buttons
    check_func_datagrabber = Button("Check")


def create_config():
    c = config()
    c.uuid = mwf.uuid
    return c

mwf.config_ui = create_config

"""
Part 3: Create a View
"""

def create_view():
    from traitsui.api import View, Item, Group, CSVListEditor
    from traitsui.menu import OKButton, CancelButton
    view = View(Group(Item(name='working_dir'),
                      Item(name='sink_dir'),
                      Item(name='crash_dir'),
                      Item(name='surf_dir'),
                      label='Directories', show_border=True),
                Group(Item(name='run_using_plugin',enabled_when='not save_script_only'),Item('save_script_only'),
                      Item(name='plugin', enabled_when="run_using_plugin"),
                      Item(name='plugin_args', enabled_when="run_using_plugin"),
                      Item(name='test_mode'), Item("timeout"),
                      label='Execution Options', show_border=True),
                Group(Item(name='subjects', editor=CSVListEditor()),
                      Item(name='base_dir'),
                      Item(name='fwhm', editor=CSVListEditor()),
                      Item(name='inputs_template'),
                      Item(name='meanfunc_template'),
                      Item(name='fsl_mat_template'),
                      Item(name='check_func_datagrabber'),
                      label='Subjects', show_border=True),
                Group(Item(name='norm_template'),
                      Item(name="do_segment"),
                      Item(name='do_anatomical_only'),
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
Part 4: Workflow Construction
"""

def func_datagrabber(c, name="resting_output_datagrabber"):
    import nipype.pipeline.engine as pe
    import nipype.interfaces.io as nio
    # create a node to obtain the functional images
    datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id',
                                                             'fwhm'],
                                                   outfields=['inputs',
                                                              'meanfunc',
                                                              'fsl_mat']),
                         name=name)
    datasource.inputs.base_directory = os.path.join(c.base_dir)
    datasource.inputs.sort_filelist = True
    datasource.inputs.template = '*'
    datasource.inputs.field_template = dict(
                                inputs=c.inputs_template,
                                meanfunc=c.meanfunc_template,
                                fsl_mat=c.fsl_mat_template)
    datasource.inputs.template_args = dict(inputs=[['subject_id', 'fwhm']],
                                           meanfunc=[['subject_id']],
                                           fsl_mat=[['subject_id']])
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
    import nipype.interfaces.utility as util
    from nipype.interfaces.io import FreeSurferSource
    import nipype.interfaces.io as nio
    if not c.do_anatomical_only:
        norm = get_full_norm_workflow()
    else:
        norm = get_struct_norm_workflow()

    fssource = pe.Node(interface=FreeSurferSource(), name='fssource')
    fssource.inputs.subjects_dir = c.surf_dir

    infosource = pe.Node(util.IdentityInterface(fields=['subject_id']),
                         name='subject_names')
    infosource.iterables = ('subject_id', c.subjects)

    infofwhm = pe.Node(util.IdentityInterface(fields=['fwhm']),
                         name='fwhm')
    infofwhm.iterables = ('fwhm', c.fwhm)

    inputspec = norm.get_node('inputspec')

    norm.connect(infosource, 'subject_id', fssource, 'subject_id')
    norm.connect(fssource, ('aparc_aseg', pickfirst),
                 inputspec, 'segmentation')
    norm.connect(fssource, 'orig', inputspec, 'brain')


    if not c.do_anatomical_only:
        datagrab = func_datagrabber(c)
        norm.connect(infosource, 'subject_id', datagrab, 'subject_id')
        norm.connect(infofwhm, 'fwhm', datagrab, 'fwhm')
        norm.connect(datagrab, 'fsl_mat', inputspec, 'out_fsl_file')
        norm.connect(datagrab, 'inputs', inputspec, 'moving_image')
        norm.connect(datagrab, 'meanfunc', inputspec, 'mean_func')

    norm.inputs.inputspec.template_file = c.norm_template

    sinkd = pe.Node(nio.DataSink(), name='sinkd')
    sinkd.inputs.base_directory = os.path.join(c.sink_dir)

    outputspec = norm.get_node('outputspec')
    norm.connect(infosource, 'subject_id', sinkd, 'container')
    norm.connect(outputspec, 'warped_brain', sinkd, 'smri.warped_brain')
    norm.connect(outputspec, 'warp_field', sinkd, 'smri.warped_field')
    norm.connect(outputspec, 'affine_transformation',
                 sinkd, 'smri.affine_transformation')
    norm.connect(outputspec, 'inverse_warp', sinkd, 'smri.inverse_warp')
    norm.connect(outputspec, 'unwarped_brain',
                 sinkd, 'smri.unwarped_brain')
    norm.connect(infosource,('subject_id',getsubstitutions),sinkd,'substitutions')

    if not c.do_anatomical_only:
        norm.connect(outputspec, 'warped_image', sinkd, 'smri.warped_image')

    if c.do_segment:
        seg = warp_segments()
        norm.connect(infosource, 'subject_id', seg, 'inputspec.subject_id')
        seg.inputs.inputspec.subjects_dir = c.surf_dir
        norm.connect(outputspec, 'warp_field', seg, 'inputspec.warp_file')
        norm.connect(outputspec, 'affine_transformation', seg, "inputspec.ants_affine")
        norm.connect(inputspec, 'template_file',seg, "inputspec.warped_brain")
        norm.connect(seg,"outputspec.out_files",sinkd,"smri.segments")

    return norm

mwf.workflow_function = normalize_workflow

"""
Part 5: Define the main function
"""

def main(config_file):
    c = load_config(config_file, create_config)

    workflow = normalize_workflow(c)
    workflow.base_dir = c.working_dir
    workflow.config = {'execution': {'crashdump_dir': c.crash_dir,"job_finished_timeout": c.timeout}}

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
Part 6: Register the Workflow
"""

register_workflow(mwf)
