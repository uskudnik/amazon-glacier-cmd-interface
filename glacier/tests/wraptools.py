#!/usr/bin/python
# Author Philip Walls, rabidgeek.com
# Downloaded from http://bzr.rabidgeek.com/boilerplate/annotate/head:
# /python/misc/wraptools/wraptools.py on 13/11/2012
import sys
import functools

"""A module to ease the replacement or wrapping of methods in modules."""

def replace_method(method, new):
	"""Replace a method with a new one in memory.

	It's important to note that this replaces *all* instances of a method
	in the parent class as well as all subclasses. If you only want to replace
	the method in a single class, just use setattr()

	Arguments:
		method: The method to replace
		new: The method to replace it with
	"""

	for o, m in get_methods(method):
		original = getattr(o, m)

		# Update the function to look like the original (doc, name, etc)
		functools.update_wrapper(new, original)

		setattr(o, m, new)


def wrap_method(method, wrapper):
	"""Wrap a method in another method.

	The original method gets passed as the first argument to the new wrapper.
	
	Arguments:
		method: The original method to wrap
		wrapper: The new wrapper method
	"""

	def new(*args, **kwargs):
		return wrapper(method, *args, **kwargs)

	replace_method(method, new)


def get_module(method):
	"""Determine the canonical module for a particular object.

	Traverses through objects until it finds an __module__ attribute.

	Arguments:
		method: The object to find the module for.

	Returns:
		A module object.
	"""

	module_name = getattr(method, '__module__', None)
	if module_name:
		module = sys.modules[module_name]
	else:
		im_class = getattr(method, 'im_class', None)
		module = get_module(im_class)

	return module


def get_subclasses(class_object):
	"""Get all subclasses for a class.

	This falls back on a bruteforce method for old style classes (ones that
	don't inherit from 'object')

	Arguments:
		class_object: A class object to retrieve subclasses of.

	Returns:
		A list of class objects.
	"""

	if hasattr(class_object, '__subclasses__'):
		for c1 in class_object.__subclasses__():
			yield c1
			for c2 in get_subclasses(c1):
				yield c2
	else:
		module = get_module(class_object)
		for c in get_subclasses_bruteforce(module, class_object):
			yield c


def get_subclasses_bruteforce(parent, class_object):
	"""A bruteforce method for getting subclasses of a class.

	This method is required for classes that don't inherit explicitly from the
	'object' class. Could probably be optimized/cleaner.

	Arguments:
		parent: The object to begin traversing from.
		class_object: A class object to retrieve subclasses of.

	Returns:
		A list of class objects.
	"""

	for v in vars(parent):
		o = getattr(parent, v)

		# If issubclass fails, it's because we're not working with a class
		try:
			isclass = issubclass(o, class_object)
		except:
			continue

		# If it's the same object we're looking for don't return it
		if o == class_object:
			continue

		if isclass:
			yield o

		# Walk through any other classes we find, regardless of if they are
		# a subclass of the original object
		for c in get_subclasses_bruteforce(o, class_object):
			yield c


def get_methods(method):
	"""Retrieve a list of methods to replace.

	This includes all instances of this method in subclasses.

	Arguments:
		method: The method to search for.

	Returns:
		A list of tuples in the form (class, attribute name).
	"""

	method_name = method.__name__

	class_object = getattr(method, 'im_class', None)
	module = get_module(method)

	if class_object:
		yield(class_object, method_name)
		for c in get_subclasses(class_object):
			yield(c, method_name)

	else:
		yield(module, method_name)


def wraps(method):
	"""A decorator for wrapping a method.

	Arguments:
		method: The method to wrap.

	Returns:
		The original decorated method.
	"""

	def wrap_object(wrapper):
		wrap_method(method, wrapper)
		return wrapper
	return wrap_object


def replaces(method):
	"""A decorator for replacing a method.

	Arguments:
		method: The method to replace.

	Returns:
		The original decorated method.
	"""

	def replace_object(new):
		replace_method(method, new)
		return new
	return replace_object

