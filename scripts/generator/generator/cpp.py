
# This file is part of the CLBlast project. The project is licensed under Apache Version 2.0. This file follows the
# PEP8 Python style guide and uses a max-width of 120 characters per line.
#
# Author(s):
#   Cedric Nugteren <www.cedricnugteren.nl>

import generator.datatype as datatype
import generator.convert as convert


NL = "\n"
SEPARATOR = "// ================================================================================================="

# Separators for the BLAS levels
LEVEL_SEPARATORS = [
    NL + SEPARATOR + NL + "// BLAS level-1 (vector-vector) routines" + NL + SEPARATOR,
    NL + SEPARATOR + NL + "// BLAS level-2 (matrix-vector) routines" + NL + SEPARATOR,
    NL + SEPARATOR + NL + "// BLAS level-3 (matrix-matrix) routines" + NL + SEPARATOR,
    NL + SEPARATOR + NL + "// Extra non-BLAS routines (level-X)" + NL + SEPARATOR
]

# Names of the level sub-folders
LEVEL_NAMES = ["1", "2", "3", "x"]

# Main header/footer for source files
FOOTER = NL + SEPARATOR + NL
HEADER = NL + SEPARATOR + """
// This file is part of the CLBlast project. The project is licensed under Apache Version 2.0. This
// project loosely follows the Google C++ styleguide and uses a tab-size of two spaces and a max-
// width of 100 characters per line.
//
// Author(s):
//   Cedric Nugteren <www.cedricnugteren.nl>
//
""" + SEPARATOR + NL


def clblast_h(routine):
    """The C++ API header (.h)"""
    result = NL + "// " + routine.description + ": " + routine.short_names() + NL
    result += routine.routine_header_cpp(12, " = nullptr") + ";" + NL
    return result


def clblast_cc(routine):
    """The C++ API implementation (.cpp)"""
    indent1 = " " * (15 + routine.length())
    result = NL + "// " + routine.description + ": " + routine.short_names() + NL
    if routine.implemented:
        result += routine.routine_header_cpp(12, "") + " {" + NL
        result += "  try {" + NL
        result += "    auto queue_cpp = Queue(*queue);" + NL
        result += "    auto routine = X" + routine.name + "<" + routine.template.template + ">(queue_cpp, event);" + NL
        result += "    routine.Do" + routine.name.capitalize() + "("
        result += ("," + NL + indent1).join([a for a in routine.arguments_clcudaapi()])
        result += ");" + NL
        result += "    return StatusCode::kSuccess;" + NL
        result += "  } catch (...) { return DispatchException(); }" + NL
    else:
        result += routine.routine_header_type_cpp(12) + " {" + NL
        result += "  return StatusCode::kNotImplemented;" + NL
    result += "}" + NL
    for flavour in routine.flavours:
        indent2 = " " * (34 + routine.length() + len(flavour.template))
        result += "template StatusCode PUBLIC_API " + routine.name.capitalize() + "<" + flavour.template + ">("
        result += ("," + NL + indent2).join([a for a in routine.arguments_type(flavour)])
        result += "," + NL + indent2 + "cl_command_queue*, cl_event*);" + NL
    return result


def clblast_c_h(routine):
    """The C API header (.h)"""
    result = NL + "// " + routine.description + ": " + routine.short_names() + NL
    for flavour in routine.flavours:
        result += routine.routine_header_c(flavour, 38, " PUBLIC_API") + ";" + NL
    return result


def clblast_c_cc(routine):
    """The C API implementation (.cpp)"""
    result = NL + "// " + routine.name.upper() + NL
    for flavour in routine.flavours:
        template = "<" + flavour.template + ">" if routine.no_scalars() else ""
        indent = " " * (16 + routine.length() + len(template))
        result += routine.routine_header_c(flavour, 27, "") + " {" + NL
        result += "  try {" + NL
        result += "    return static_cast<CLBlastStatusCode>(" + NL
        result += "      clblast::" + routine.name.capitalize() + template + "("
        result += ("," + NL + indent).join([a for a in routine.arguments_cast(flavour, indent)])
        result += "," + NL + indent + "queue, event)" + NL
        result += "    );" + NL
        result += "  } catch (...) { return static_cast<CLBlastStatusCode>(clblast::DispatchExceptionForC()); }" + NL
        result += "}" + NL
    return result


def clblast_netlib_c_h(routine):
    """The Netlib CBLAS API header (.h)"""
    result = NL + "// " + routine.description + ": " + routine.short_names() + NL
    for flavour in routine.flavours:
        if flavour.precision_name in ["S", "D", "C", "Z"]:
            result += routine.routine_header_netlib(flavour, 24, " PUBLIC_API") + ";" + NL
    return result


def clblast_netlib_c_cc(routine):
    """The Netlib CBLAS API implementation (.cpp)"""
    result = NL + "// " + routine.name.upper() + NL
    for flavour in routine.flavours:

        # There is a version available in CBLAS
        if flavour.precision_name in ["S", "D", "C", "Z"]:
            template = "<" + flavour.template + ">" if routine.no_scalars() else ""
            indent = " " * (21 + routine.length() + len(template))
            result += routine.routine_header_netlib(flavour, 13, "") + " {" + NL

            # Initialize OpenCL
            result += "  auto device = get_device();" + NL
            result += "  auto context = clblast::Context(device);" + NL
            result += "  auto queue = clblast::Queue(context, device);" + NL

            # Set alpha and beta
            result += "".join("  " + s + NL for s in routine.scalar_create_cpp(flavour))

            # Copy data structures to the device
            for i, name in enumerate(routine.inputs + routine.outputs):
                result += "  " + routine.set_size(name, routine.buffer_sizes[i]) + NL
            for i, name in enumerate(routine.inputs + routine.outputs):
                result += "  " + routine.create_buffer(name, flavour.buffer_type) + NL
            for name in routine.inputs + routine.outputs:
                prefix = "" if name in routine.outputs else "const "
                result += "  " + routine.write_buffer(name, prefix + flavour.buffer_type) + NL

            # The function call
            result += "  auto queue_cl = queue();" + NL
            result += "  auto s = clblast::" + routine.name.capitalize() + template + "("
            result += ("," + NL + indent).join([a for a in routine.arguments_netlib(flavour, indent)])
            result += "," + NL + indent + "&queue_cl);" + NL

            # Error handling
            result += "  if (s != clblast::StatusCode::kSuccess) {" + NL
            result += "    throw std::runtime_error(\"CLBlast returned with error code \" + clblast::ToString(s));" + NL
            result += "  }" + NL

            # Copy back and clean-up
            for name in routine.outputs:
                result += "  " + routine.read_buffer(name, flavour.buffer_type) + NL
            result += "}" + NL
    return result


def wrapper_clblas(routine):
    """The wrapper to the reference clBLAS routines (for performance/correctness testing)"""
    result = ""
    if routine.has_tests:
        result += NL + "// Forwards the clBLAS calls for %s" % routine.short_names_tested() + NL
        if routine.no_scalars():
            result += routine.routine_header_wrapper_clblas(routine.template, True, 21) + ";" + NL
        for flavour in routine.flavours:
            result += routine.routine_header_wrapper_clblas(flavour, False, 21) + " {" + NL

            # There is a version available in clBLAS
            if flavour.precision_name in ["S", "D", "C", "Z"]:
                indent = " " * (17 + routine.length())
                arguments = routine.arguments_wrapper_clblas(flavour)
                if routine.scratch:
                    result += "  auto queue = Queue(queues[0]);" + NL
                    result += "  auto context = queue.GetContext();" + NL
                    result += "  auto scratch_buffer = Buffer<" + flavour.template + ">"
                    result += "(context, " + routine.scratch + ");" + NL
                    arguments += ["scratch_buffer()"]
                result += "  return clblas" + flavour.name + routine.name + "("
                result += ("," + NL + indent).join([a for a in arguments])
                result += "," + NL + indent + "num_queues, queues, num_wait_events, wait_events, events);"

            # There is no clBLAS available, forward the call to one of the available functions
            else:  # Half-precision
                indent = " " * (24 + routine.length())

                # Convert to float (note: also integer buffers are stored as half/float)
                for buf in routine.inputs + routine.outputs:
                    result += "  auto " + buf + "_buffer_bis = HalfToFloatBuffer(" + buf + "_buffer, queues[0]);" + NL

                # Call the float routine
                result += "  auto status = clblasX" + routine.name + "("
                result += ("," + NL + indent).join([a for a in routine.arguments_half()])
                result += "," + NL + indent + "num_queues, queues, num_wait_events, wait_events, events);"
                result += NL

                # Convert back to half
                for buf in routine.outputs:
                    result += "  FloatToHalfBuffer(" + buf + "_buffer, " + buf + "_buffer_bis, queues[0]);" + NL
                result += "  return status;"

            # Complete
            result += NL + "}" + NL
    return result


def wrapper_cblas(routine):
    """The wrapper to the reference CBLAS routines (for performance/correctness testing)"""
    result = ""
    if routine.has_tests:
        result += NL + "// Forwards the Netlib BLAS calls for %s" % routine.short_names_tested() + NL
        for flavour in routine.flavours:
            result += routine.routine_header_wrapper_cblas(flavour, 12) + " {" + NL

            # There is a version available in CBLAS
            if flavour.precision_name in ["S", "D", "C", "Z"]:
                indent = " " * (10 + routine.length())
                arguments = routine.arguments_wrapper_cblas(flavour)

                # Complex scalars
                for scalar in routine.scalars:
                    if flavour.is_complex(scalar):
                        result += "  const auto " + scalar + "_array = std::vector<" + flavour.buffer_type[:-1] + ">"
                        result += "{" + scalar + ".real(), " + scalar + ".imag()};" + NL

                # Special case for scalar outputs
                assignment = ""
                postfix = ""
                end_of_line = ""
                extra_argument = ""
                for output_buffer in routine.outputs:
                    if output_buffer in routine.scalar_buffers_first():
                        if flavour in [datatype.C, datatype.Z]:
                            postfix += "_sub"
                            indent += "    "
                            extra_argument += "," + NL + indent
                            extra_argument += "reinterpret_cast<return_pointer_" + flavour.buffer_type[:-1] + ">"
                            extra_argument += "(&" + output_buffer + "_buffer[" + output_buffer + "_offset])"
                        elif output_buffer in routine.index_buffers():
                            assignment = "((int*)&" + output_buffer + "_buffer[0])[" + output_buffer + "_offset] = "
                            indent += " " * len(assignment)
                        else:
                            assignment = output_buffer + "_buffer[" + output_buffer + "_offset]"
                            if flavour.name in ["Sc", "Dz"]:
                                assignment += ".real("
                                end_of_line += ")"
                            else:
                                assignment += " = "
                            indent += " " * len(assignment)

                result += "  " + assignment + "cblas_" + flavour.name.lower() + routine.name + postfix + "("
                result += ("," + NL + indent).join([a for a in arguments])
                result += extra_argument + end_of_line + ");" + NL

            # There is no CBLAS available, forward the call to one of the available functions
            else:  # Half-precision
                indent = " " * (9 + routine.length())

                # Convert to float (note: also integer buffers are stored as half/float)
                for buf in routine.inputs + routine.outputs:
                    result += "  auto " + buf + "_buffer_bis = HalfToFloatBuffer(" + buf + "_buffer);" + NL

                # Call the float routine
                result += "  cblasX" + routine.name + "("
                result += ("," + NL + indent).join([a for a in routine.arguments_half()])
                result += ");" + NL

                # Convert back to half
                for buf in routine.outputs:
                    result += "  FloatToHalfBuffer(" + buf + "_buffer, " + buf + "_buffer_bis);" + NL

            # Complete
            result += "}" + NL
    return result


def performance_test(routine, level_string):
    """Generates the body of a performance test for a specific routine"""
    result = ""
    result += "#include \"test/performance/client.hpp\"" + NL
    result += "#include \"test/routines/level" + level_string + "/x" + routine.name + ".hpp\"" + NL + NL
    result += "// Shortcuts to the clblast namespace" + NL
    result += "using float2 = clblast::float2;" + NL
    result += "using double2 = clblast::double2;" + NL + NL
    result += "// Main function (not within the clblast namespace)" + NL
    result += "int main(int argc, char *argv[]) {" + NL
    default = convert.precision_to_full_name(routine.flavours[0].precision_name)
    result += "  switch(clblast::GetPrecision(argc, argv, clblast::Precision::k" + default + ")) {" + NL
    for precision in ["H", "S", "D", "C", "Z"]:
        result += "    case clblast::Precision::k" + convert.precision_to_full_name(precision) + ":"
        found = False
        for flavour in routine.flavours:
            if flavour.precision_name == precision:
                result += NL + "      clblast::RunClient<clblast::TestX" + routine.name + flavour.test_template()
                result += ">(argc, argv); break;" + NL
                found = True
        if not found:
            result += " throw std::runtime_error(\"Unsupported precision mode\");" + NL
    result += "  }" + NL
    result += "  return 0;" + NL
    result += "}" + NL
    return result


def correctness_test(routine, level_string):
    """Generates the body of a correctness test for a specific routine"""
    result = ""
    result += "#include \"test/correctness/testblas.hpp\"" + NL
    result += "#include \"test/routines/level" + level_string + "/x" + routine.name + ".hpp\"" + NL + NL
    result += "// Shortcuts to the clblast namespace" + NL
    result += "using float2 = clblast::float2;" + NL
    result += "using double2 = clblast::double2;" + NL + NL
    result += "// Main function (not within the clblast namespace)" + NL
    result += "int main(int argc, char *argv[]) {" + NL
    result += "  auto errors = size_t{0};" + NL
    not_first = "false"
    for flavour in routine.flavours:
        result += "  errors += clblast::RunTests<clblast::TestX" + routine.name + flavour.test_template()
        result += ">(argc, argv, " + not_first + ", \"" + flavour.name + routine.name.upper() + "\");" + NL
        not_first = "true"
    result += "  if (errors > 0) { return 1; } else { return 0; }" + NL
    result += "}" + NL
    return result
