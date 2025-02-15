import pydrake.planning as mut

import unittest

from pydrake.common import FindResourceOrThrow
from pydrake.common.test_utilities import numpy_compare
from pydrake.geometry import SceneGraph_
from pydrake.multibody.parsing import Parser
from pydrake.multibody.plant import MultibodyPlant_
from pydrake.systems.framework import Context_, DiagramBuilder_


class TestRobotDiagram(unittest.TestCase):
    @numpy_compare.check_all_types
    def test_robot_diagram_builder(self, T):
        """Tests the full RobotDiagramBuilder API.
        """
        Class = mut.RobotDiagramBuilder_[T]
        dut = Class(time_step=0.0)
        if T == float:
            # Most users would use the mutable_parser function.
            dut.mutable_parser().AddModels(FindResourceOrThrow(
                "drake/manipulation/models/iiwa_description/urdf/"
                "iiwa14_spheres_dense_collision.urdf"))
            # Sanity check that this is bound. There are currently no const
            # functions defined by Parser, so it's somewehat useless.
            self.assertIsInstance(dut.parser(), Parser)
        else:
            # TODO(jwnimmer-tri) Use dut.mutable_plant() to manually add some
            # models, bodies, and geometries here.
            pass

        # Sanity check all of the accessors.
        self.assertIsInstance(dut.mutable_builder(), DiagramBuilder_[T])
        self.assertIsInstance(dut.builder(), DiagramBuilder_[T])
        self.assertIsInstance(dut.mutable_plant(), MultibodyPlant_[T])
        self.assertIsInstance(dut.plant(), MultibodyPlant_[T])
        self.assertIsInstance(dut.mutable_scene_graph(), SceneGraph_[T])
        self.assertIsInstance(dut.scene_graph(), SceneGraph_[T])

        # Finalize.
        self.assertFalse(dut.IsPlantFinalized())
        dut.FinalizePlant()
        self.assertTrue(dut.IsPlantFinalized())

        # Build.
        self.assertFalse(dut.IsDiagramBuilt())
        diagram = dut.BuildDiagram()
        self.assertTrue(dut.IsDiagramBuilt())
        self.assertIsInstance(diagram, mut.RobotDiagram_[T])

    @numpy_compare.check_all_types
    def test_robot_diagram(self, T):
        """Tests the full RobotDiagram API.
        """
        builder = mut.RobotDiagramBuilder_[T]()
        dut = builder.BuildDiagram()

        self.assertIsInstance(dut.plant(), MultibodyPlant_[T])
        self.assertIsInstance(dut.mutable_scene_graph(), SceneGraph_[T])
        self.assertIsInstance(dut.scene_graph(), SceneGraph_[T])

        root_context = dut.CreateDefaultContext()
        self.assertIsInstance(
            dut.mutable_plant_context(root_context=root_context),
            Context_[T])
        self.assertIsInstance(
            dut.plant_context(root_context=root_context),
            Context_[T])
        self.assertIsInstance(
            dut.mutable_scene_graph_context(root_context=root_context),
            Context_[T])
        self.assertIsInstance(
            dut.scene_graph_context(root_context=root_context),
            Context_[T])
