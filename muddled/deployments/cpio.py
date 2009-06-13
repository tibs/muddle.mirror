"""
cpio deployment.

Most commonly used to create Linux ramdisks, this 
deployment creates a CPIO archive from the relevant
install directory and applies the relevant instructions.

Because python has no native CPIO support, we need to
do this by creating a tar archive and then invoking
cpio in copy-through mode to convert the archive to
cpio. Ugh.
"""


import muddled
import muddled.pkg as pkg
import muddled.env_store
import muddled.depend as depend
import muddled.utils as utils
import muddled.filespec as filespec
import muddled.deployment as deployment
import muddled.cpiofile as cpiofile
import os

class CpioInstructionImplementor:
    def apply(self, builder, instruction, role, path):
        pass

class CpioDeploymentBuilder(pkg.Dependable):
    """
    Builds the specified CPIO deployment
    """
    
    def __init__(self, roles, builder, target_file, target_base):
        self.builder = builder
        self.target_file = target_file
        self.target_base = target_base
        self.roles = roles

    def attach_env(self):
        """
        Attaches an environment containing:
        
        MUDDLE_TARGET_LOCATION   the location in the target filesystem where 
                                  this deployment will end up.

        To every package label in this role.
        """
        
        for role in self.roles:
            lbl = depend.Label(utils.LabelKind.Package,
                               "*",
                               role,
                               "*")
            env = self.builder.invocation.get_environment_for(lbl)
        
            env.set_type("MUDDLE_TARGET_LOCATION", muddled.env_store.EnvType.SimpleValue)
            env.set("MUDDLE_TARGET_LOCATION", self.target_base)
    


    def build_label(self,label):
        """
        Actually cpio everything up, following instructions appropriately
        """
        
        if (label.tag == utils.Tags.Deployed):
            # Collect all the relevant files ..
            deploy_dir = self.builder.invocation.deploy_path(label.name)
            deploy_file = os.path.join(deploy_dir,
                                       self.target_file)

            utils.ensure_dir(os.path.dirname(deploy_file))

            
            the_heirarchy = cpiofile.Heirarchy({ }, { })
            for r in self.roles:
                m = cpiofile.heirarchy_from_fs(self.builder.invocation.role_install_path(r), 
                                               self.target_base)
                the_heirarchy.merge(m)

            app_dict = get_instruction_dict()

            # Apply instructions .. 
            for role in self.roles:
                lbl = depend.Label(utils.LabelKind.Package, "*", role, "*")
                instr_list = self.builder.load_instructions(lbl)
                for (lbl, fn, instrs) in instr_list:
                    print "Applying instructions for role %s, label %s .. "%(role, lbl)
                    for instr in instrs:
                        iname = instr.outer_elem_name()
                        if (iname in app_dict):
                            app_dict[iname].apply(self.builder, instr, role, the_heirarchy)
                        else:
                            raise utils.Failure("CPIO deployments don't know about " + 
                                                "the instruction %s (lbl %s, file %s"%(iname, lbl, fn))
            # .. and write the file.
            print "> Writing %s .. "%deploy_file
            the_heirarchy.render(deploy_file, True)
        else:
            raise utils.Failure("Attempt to build a cpio deployment with unknown label %s"%(lbl))

class CIApplyChmod(CpioInstructionImplementor):
    def apply(self, builder, instr, role, heirarchy):
        dp = cpiofile.CpioFileDataProvider(heirarchy)
        files = dp.abs_match(instr.filespec)
        
        for f in files:
            # For now ..
            f.mode = instr.new_mode

class CIApplyChown(CpioInstructionImplementor):
    def apply(self, builder, instr, role, heirarchy):
        dp = cpiofile.CpioFileDataProvider(heirarchy)
        files = dp.abs_match(instr.filespec)

        for f in files:
            if (instr.new_user is not None):
                f.uid = instr.new_user
            if (instr.new_group is not None):
                f.gid = instr.new_group

def get_instruction_dict():
    """
    Return a dictionary mapping the names of insrtuctions to the
    classes that implement them
    """
    app_dict = { }
    app_dict["chown"] = CIApplyChown()
    app_dict["chmod"] = CIApplyChmod()
    return app_dict

def deploy(builder, target_file, target_base, name, roles):
    """
    Set up a cpio deployment

    @param target_file   Where, relative to the deployment directory, should the
                          build cpio file end up?
    @param target_base   Where should we expect to unpack the CPIO file to?
    """
    
    the_dependable = CpioDeploymentBuilder(roles, builder, target_file, 
                                           target_base)
    
    dep_label = depend.Label(utils.LabelKind.Deployment,
                             name, None,
                             utils.Tags.Deployed)

    deployment_rule = depend.Rule(dep_label, the_dependable)
    for role in roles:
        role_label = depend.Label(utils.LabelKind.Package,
                                  "*",
                                  role,
                                  utils.Tags.PostInstalled)
        deployment_rule.add(role_label)

    builder.invocation.ruleset.add(deployment_rule)

    the_dependable.attach_env()
    
    # Cleanup is generic
    deployment.register_cleanup(builder, name)

# End file.


        