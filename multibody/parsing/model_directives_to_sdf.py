# Copyright 2022 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import yaml
import warnings
import argparse
import lxml.etree as ET
from typing import Any, Dict, List

# TODO(aaronchongth): Check for simple validity of output model XML, whether the
# model just has a single joint or something, without any other mandatory model
# elements.

SDF_VERSION = '1.9'
SCOPE_DELIMITER = '::'
WORLD_FRAME = 'world'

# MODEL_ELEM_MAP has the scoped model name as the key and its
# corresponding XML element root as the value. This is used in
# add_directives where model namespaces is defined, in add_model, as well as
# when model elements are constructed due to implicit or explicit frame
# names.
MODEL_ELEM_MAP = {}

# INCOMPLETE_MODELS is a list that contains all model names of model elements
# that have been constructed but not yet valid (completed). This is for
# keeping track that all model elements are properly populated and not left
# empty. They are constructed using add_model_instance or add_frame with scoped
# names.
INCOMPLETE_MODELS = []

# CHILD_FRAME_MODEL_NAME_TO_WELD_MAP maps the top model instance name of the
# child frame (in each weld) to the weld directive itself. This map is used
# for posturing frames as the placement_frame and pose combination is needed.
CHILD_FRAME_MODEL_NAME_TO_WELD_MAP = {}

# def add_directives(root: ET, directive: Dict[str, Any],
#                    add_model_instance_elem_map: Dict[str, Any],
#                    added_model_instances: List[str],
#                    child_model_instance_to_weld_map: Dict[str, Dict[str, str]]
#                   ) -> bool:
#     include_elem = None
#     if 'model_namespace' in directive:
#         model_ns = directive['model_namespace']
#         if model_ns not in added_model_instances:
#             print(f'Requested model namespace {model_ns} has not been '
#                   'constructed.')
#             return False
# 
#         if model_ns not in add_model_instance_elem_map:
#             print('The XML element of the requested model namespace '
#                   f'{model_ns} has not been constructed.')
#             return False
# 
#         added_model_instances.remove(model_ns)
#         model_elem = add_model_instance_elem_map[model_ns]
#         include_elem = ET.SubElement(model_elem, 'include', merge='true')
# 
#         if model_ns in child_model_instance_to_weld_map:
#             weld = child_model_instance_to_weld_map.pop(model_ns)
#             placement_frame_name = \
#                 weld['child'][len(model_ns)+len(SCOPE_DELIMITER):]
#             include_elem.set('placement_frame', placement_frame_name)
#             pose_elem = ET.SubElement(include_elem, 'pose',
#                                       relative_to=weld['parent'])
# 
#     else:
#         include_elem = ET.SubElement(root, 'include', merge='true')
# 
#     file_path = directive['file']
#     # Assumption: the included directive file has been converted to the same
#     # name in the same location but with a .sdf extension.
#     sdf_file_path = file_path.replace('.yaml', '.sdf')
# 
#     uri_elem = ET.SubElement(include_elem, 'uri')
#     uri_elem.text = sdf_file_path
#     return True


def add_model(root: ET, directive: Dict[str, Any]) -> bool:
    model_root = root
    model_name = directive['name']
    file_name = directive['file']

    include_elem = None

    # If the model element has already been constructed due to add_frame, the
    # file is merge included.
    if model_name in MODEL_ELEM_MAP:
        model_root = MODEL_ELEM_MAP[model_name]
        include_elem = ET.SubElement(model_root, 'include', merge='true')

        if model_name in INCOMPLETE_MODELS:
            INCOMPLETE_MODELS.remove(model_name)
    else:
        include_elem = ET.SubElement(model_root, 'include')

    name_elem = ET.SubElement(include_elem, 'name')
    name_elem.text = model_name

    uri_elem = ET.SubElement(include_elem, 'uri')
    uri_elem.text = file_name

    if model_name not in CHILD_FRAME_MODEL_NAME_TO_WELD_MAP:
        return True

    # If this model contains a frame used in an add_weld instance, we use the
    # placement_frame and pose combination to posture it.
    weld = CHILD_FRAME_MODEL_NAME_TO_WELD_MAP.pop(model_name)
    placement_frame_elem = ET.SubElement(include_elem, 'placement_frame')
    placement_frame_elem.text = \
        weld['child'][len(model_name)+len(SCOPE_DELIMITER):]
    pose_elem = ET.SubElement(include_elem, 'pose', relative_to=weld['parent'])
    return True


# NOTE(aaronchongth):
# * we can create scopes all the way down both implicit based on
# X_PF base_frame, as well as explicit based on the scoped names,
# how do we make sure that there is no scope violation? The base_frame
# could be on A, however the explicit scope could be in A::B::C, the
# frame element will then be constructed in a nested manner but
# referencing a frame that is at the top.
# * one solution would be comparing the explicit scoped name's scope,
# with the scope of the base_frame, only if the base_frame lives
# beneath the scoped_name's scope
# (name: A::B::name, base_frame: A::B::C::frame)
# or on the same level
# (name: A::B::name, base_frame: A::B::frame), will it be allowed.
# * in the implicit case, (name: name, base_frame: A::B::frame), the
# frame will be constructed as
# (name: A::B::name, base_frame: A::B::frame).
def add_frame(root: ET, directive: Dict[str, Any]) -> bool:
    scoped_frame_name = directive['name']
    split_frame_name = scoped_frame_name.split(SCOPE_DELIMITER)

    x_pf = directive['X_PF']
    scoped_base_frame = x_pf['base_frame']
    if scoped_base_frame == WORLD_FRAME:
        print(f'Workflows where base frame "{WORLD_FRAME}" exist is not '
              'supported to be converted using this script.')
        return False
    split_base_frame_name = scoped_base_frame.split(SCOPE_DELIMITER)

    # Implicit case, we append the frame to the scope of the base frame.
    if len(split_frame_name) == 1 and len(split_base_frame_name) > 1:
        scopes = split_base_frame_name[:-1]
        scopes.append(split_frame_name[0])
        split_frame_name = scopes
    # Explicit case: frame is nested more than its base_frame.
    elif len(split_frame_name) > len(split_base_frame_name):
        print(f'Frame [{scoped_frame_name}] is being added explicitly at a '
              f'more nested level than its base_frame [{scoped_base_frame}]. '
              'This violates scoping rules in sdformat, and the workflow '
              'should be modified.')
        return False
    # Explicit case: base_frame is nested more than the frame, we check that
    # they have a common scope, so that the base_frame is reachable when the
    # frame is constructed.
    elif len(split_frame_name) <= len(split_base_frame_name):
        for i in range(len(split_frame_name)-1):
            if split_frame_name[i] != split_base_frame_name[i]:
                print(f'Frame [{scoped_frame_name}] and its base_frame '
                      f'[{scoped_base_frame}] do not share a common scope, '
                      'the base_frame will be unreachable when the frame is '
                      'constructed.')
                return False

    # scoped_base_frame must now be relative to where the frame is constructed.
    split_relative_base_frame = \
            split_base_frame_name[len(split_frame_name) - 1:]
    scoped_base_frame = SCOPE_DELIMITER.join(split_relative_base_frame)

    # Construct the necessary model scopes.
    current_model_scope = None
    model_root = root
    for scope in split_frame_name[:-1]:
        if current_model_scope is None:
            current_model_scope = scope
        else:
            current_model_scope += SCOPE_DELIMITER + scope

        # Check if the scope already exists, if it is change model_root and move
        # on.
        if current_model_scope in MODEL_ELEM_MAP:
            model_root = MODEL_ELEM_MAP[current_model_scope]
            continue

        # If not, we create it, save it to map and incomplete.
        new_model_root = ET.SubElement(model_root, 'model', name=scope)
        MODEL_ELEM_MAP[current_model_scope] = new_model_root
        model_root = new_model_root

    # We only consider the most nested model scope as incomplete, since all the
    # parent model instances will be considered valid when the nested model is
    # valid.
    if current_model_scope is not None and \
            current_model_scope not in INCOMPLETE_MODELS:
        INCOMPLETE_MODELS.append(current_model_scope)

    # Start constructing the frame in the model instance.
    translation_str = '0 0 0'
    if 'translation' in x_pf:
        trans = x_pf['translation']
        translation_str = f'{trans[0]} {trans[1]} {trans[2]}'

    # TODO(aaronchongth): Support rotations, see drake/common/schema/transform.h
    rotation_str = '0 0 0'

    frame_name = split_frame_name[-1]
    frame_elem = ET.SubElement(model_root, 'frame', name=frame_name)

    pose_elem = ET.SubElement(frame_elem, 'pose', relative_to=scoped_base_frame)
    pose_elem.text = f'{translation_str}   {rotation_str}'
    return True


# For add_weld, we only support child frames that can be referred to within the
# same sdformat file that are nested only once, as we would require the
# placement_frame and pose combination for posturing.
#
# Supported example:
# add_model:
#   name: simple_model
#   file: ...
# add_weld:
#   parent: ...
#   child: simple_model::frame
#
# Unsupported example:
# add_model:
#   name: simple_model
#   file: ...
# add_weld:
#   parent: ...
#   child: simple_model::nested_model::frame
#
# Unsupported example:
# add_directives:
#   file: directive_that_contains_simple_model.yaml
# add_weld:
#   parent: ...
#   child: simple_model::frame
#
# Whenever the top model instance in the child of the weld cannot be referred to
# obviously, this conversion will fail. In the unsupported example above, it is
# unclear where simple_model is located, hence the placement_frame and pose
# combination cannot be applied for posturing.
def add_weld_fixed_joint(root: ET, directive: Dict[str, Any]) -> bool:
    """Welding fixes two frames in the same global pose, and adds a fixed joint
    between them"""
    parent_name = directive['parent']
    child_name = directive['child']

    joint_name = \
        f'{parent_name.replace(SCOPE_DELIMITER, "__")}___to___' \
        f'{child_name.replace(SCOPE_DELIMITER, "__")}___weld_joint'

    joint_elem = ET.SubElement(root, 'joint', name=joint_name)
    joint_elem.set('type', 'fixed')

    parent_elem = ET.SubElement(joint_elem, 'parent')
    parent_elem.text = parent_name

    child_elem = ET.SubElement(joint_elem, 'child')
    child_elem.text = child_name
    return True


def convert_directive(input_path: str, output_path: str) -> None:
    # Initialize the sdformat XML root
    root = ET.Element('sdf', version=SDF_VERSION)
    root_model_name = os.path.splitext(os.path.basename(input_path))[0]
    root_model_elem = ET.SubElement(root, 'model', name=root_model_name)

    # Read the directives file
    with open(input_path, 'r') as f:
        directives = yaml.safe_load(f)
    if 'directives' not in directives:
        print('No directives found, exiting.')
        return

    # Obtain the list of directives
    directives = directives['directives']

    # Construct all new model instances and start keeping track of welds to be
    # added.
    leftover_directives = []
    for directive in directives:
        if 'add_model_instance' in directive:
            new_model_name = directive['add_model_instance']['name']
            if new_model_name in MODEL_ELEM_MAP or \
                    new_model_name in INCOMPLETE_MODELS:
                print(f'Model instance [{new_model_name}] already added')
                return
            
            new_model_elem = ET.SubElement(root_model_elem, 'model',
                                           name=new_model_name)
            MODEL_ELEM_MAP[new_model_name] = new_model_elem
            INCOMPLETE_MODELS.append(new_model_name)

        elif 'add_weld' in directive:
            weld = directive['add_weld']
            weld_child = weld['child']
            weld_child_scopes = weld_child.split(SCOPE_DELIMITER)
            if len(weld_child_scopes) != 2:
                print('Child frame in weld must be nested in a model in order '
                      'for it to be postured correctly in a weld.')
                return

            if not add_weld_fixed_joint(root_model_elem,
                                        directive['add_weld']):
                print('Failed to convert add_weld directive.')
                return

            # Bookkeeping for posturing models that are added later.
            CHILD_FRAME_MODEL_NAME_TO_WELD_MAP[weld_child_scopes[0]] = weld

        else:
            leftover_directives.append(directive)

    
    # Next, frame elements and all their model instances will be constructed.
    # This cannot be done in the same loop as above since we require all added
    # model instances to be known.
    directives = leftover_directives
    leftover_directives = []
    for directive in directives:
        if 'add_frame' in directive:
            if not add_frame(root_model_elem, directive['add_frame']):
                print('Failed to perform add_frame directive.')
                return
        leftover_directives.append(directive)

    # Go through each directive add to XML as needed.
    directives = leftover_directives
    for directive in directives:
        success = True
        if 'add_model' in directive:
            success = add_model(root_model_elem, directive['add_model'])
    #     elif 'add_directives' in directive:
    #         success = add_directives(root_model_elem,
    #                                  directive['add_directives'],
    #                                  add_model_instance_elem_map,
    #                                  added_model_instances,
    #                                  child_model_instance_to_weld_map)

        if not success:
            print(f'Failed to convert model directive {input_path}')
            return

    # Check if all the welds and incomplete model instances are taken care of.
    if CHILD_FRAME_MODEL_NAME_TO_WELD_MAP:
        print('There are welds that are still not postured properly:')
        for key in CHILD_FRAME_MODEL_NAME_TO_WELD_MAP:
            print(f'    {child_model_instance_to_weld_map[key]}')
        return

    if len(INCOMPLETE_MODELS) != 0:
        print('There are models that are generated but not used:')
        for m in INCOMPLETE_MODELS:
            print(f'    {m}')
        return

    tree = ET.ElementTree(root)
    tree.write(output_path, encoding='utf-8', xml_declaration=True,
            pretty_print=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
            '-m', '--model-directives', type=str,
            help='Path to model directives file to be converted.')
    parser.add_argument(
            '-o', '--output', type=str,
            help='Output path for converted sdformat file.')
    args = parser.parse_args()

    convert_directive(args.model_directives, args.output)
    

if __name__ == '__main__':
    main()
